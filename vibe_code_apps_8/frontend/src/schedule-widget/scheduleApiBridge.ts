import { eachDayOfInterval, format, parseISO } from "date-fns";
import type { BacnetPoint, DayName, HolidayEntry, ScheduleProfile, WeekFormState } from "./shared/scheduleTypes";
import { DAYS } from "./shared/scheduleTypes";
import { timeToMinutes } from "./shared/scheduleUtils";

export type ApiDayKey = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";

export type ApiWeeklyRow = {
  occupied: boolean;
  startMinutes: number;
  endMinutes: number;
};

export type ApiScheduleItem = {
  id: string;
  label: string;
  description?: string;
  assignments: string[];
  weekly: Partial<Record<ApiDayKey, ApiWeeklyRow>>;
  holidays: unknown[];
  bacnetBindings: {
    id: string;
    pointId: string;
    name: string;
    objectId?: string | null;
  }[];
};

export type ApiScheduleDoc = {
  version?: number;
  timezone?: string;
  hostedScheduleName?: string;
  schedules: ApiScheduleItem[];
};

const DAY_TO_API: Record<DayName, ApiDayKey> = {
  Sunday: "sun",
  Monday: "mon",
  Tuesday: "tue",
  Wednesday: "wed",
  Thursday: "thu",
  Friday: "fri",
  Saturday: "sat",
};

const API_TO_DAY: Record<ApiDayKey, DayName> = {
  sun: "Sunday",
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
  sat: "Saturday",
};

const API_DAY_KEYS: ApiDayKey[] = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

function minutesToTime(m: number): string {
  const clamped = Math.max(0, Math.min(24 * 60 - 1, Math.round(m)));
  const hh = Math.floor(clamped / 60);
  const mi = clamped % 60;
  return `${String(hh).padStart(2, "0")}:${String(mi).padStart(2, "0")}`;
}

function defaultWeekForm(): WeekFormState {
  const run = (): WeekFormState[DayName] => ({
    noSchedule: false,
    start: "08:00",
    end: "17:00",
  });
  const off = (): WeekFormState[DayName] => ({
    noSchedule: true,
    start: "08:00",
    end: "17:00",
  });
  return {
    Sunday: off(),
    Monday: run(),
    Tuesday: run(),
    Wednesday: run(),
    Thursday: run(),
    Friday: run(),
    Saturday: off(),
  };
}

function weeklyToForm(weekly: Partial<Record<ApiDayKey, unknown>>): WeekFormState {
  const form = {} as WeekFormState;
  for (const day of DAYS) {
    const key = DAY_TO_API[day];
    const row = weekly[key];
    const r = row && typeof row === "object" ? (row as Record<string, unknown>) : {};
    const occupied = Boolean(r.occupied);
    const startM = Number(r.startMinutes ?? 8 * 60);
    const endM = Number(r.endMinutes ?? 17 * 60);
    form[day] = {
      noSchedule: !occupied,
      start: minutesToTime(Number.isFinite(startM) ? startM : 8 * 60),
      end: minutesToTime(Number.isFinite(endM) ? endM : 17 * 60),
    };
  }
  return form;
}

function parseHolidaysFromApi(raw: unknown[]): HolidayEntry[] {
  const out: HolidayEntry[] = [];
  const seen = new Set<string>();
  for (const h of raw) {
    if (!h || typeof h !== "object") continue;
    const o = h as Record<string, unknown>;
    const occ = Boolean(o.occupied);
    const unoccupied = !occ;
    if (typeof o.date === "string" && o.date) {
      const dateStr = o.date;
      if (seen.has(dateStr)) continue;
      seen.add(dateStr);
      out.push({
        id: typeof o.id === "string" && o.id ? o.id : crypto.randomUUID(),
        date: dateStr,
        unoccupied,
      });
      continue;
    }
    const startS = typeof o.start === "string" ? o.start : "";
    if (!startS) continue;
    const endS = typeof o.end === "string" && o.end ? o.end : startS;
    try {
      const start = parseISO(startS);
      const end = parseISO(endS);
      const days = eachDayOfInterval({ start, end });
      for (const d of days) {
        const dateStr = format(d, "yyyy-MM-dd");
        if (seen.has(dateStr)) continue;
        seen.add(dateStr);
        out.push({
          id: crypto.randomUUID(),
          date: dateStr,
          unoccupied,
        });
      }
    } catch {
      /* skip invalid range */
    }
  }
  out.sort((a, b) => a.date.localeCompare(b.date));
  return out;
}

function bindingsToPoints(bindings: ApiScheduleItem["bacnetBindings"]): BacnetPoint[] {
  if (!bindings.length) return [];
  return bindings.map((b) => ({
    id: String(b.id || b.pointId),
    name: String(b.name || b.pointId),
    objectId: b.objectId ? String(b.objectId) : undefined,
  }));
}

export function docToProfiles(doc: ApiScheduleDoc): ScheduleProfile[] {
  const list = Array.isArray(doc.schedules) ? doc.schedules : [];
  if (!list.length) {
    const id = crypto.randomUUID();
    return [
      {
        id,
        name: "Default",
        form: defaultWeekForm(),
        bacnetPoints: [],
        holidays: [],
      },
    ];
  }
  return list.map((s) => ({
    id: String(s.id || crypto.randomUUID()),
    name: String(s.label || "Schedule"),
    form: weeklyToForm(s.weekly ?? {}),
    bacnetPoints: bindingsToPoints(s.bacnetBindings ?? []),
    holidays: parseHolidaysFromApi(s.holidays ?? []),
  }));
}

function formToWeekly(form: WeekFormState): Record<ApiDayKey, ApiWeeklyRow> {
  const weekly = {} as Record<ApiDayKey, ApiWeeklyRow>;
  for (const key of API_DAY_KEYS) {
    const day = API_TO_DAY[key];
    const row = form[day];
    if (row.noSchedule) {
      weekly[key] = { occupied: false, startMinutes: 8 * 60, endMinutes: 17 * 60 };
    } else {
      weekly[key] = {
        occupied: true,
        startMinutes: timeToMinutes(row.start),
        endMinutes: timeToMinutes(row.end),
      };
    }
  }
  return weekly;
}

function holidaysToApi(entries: HolidayEntry[]): Record<string, unknown>[] {
  return entries.map((h) => ({
    id: h.id,
    date: h.date,
    occupied: !h.unoccupied,
  }));
}

function pointsToBindings(points: BacnetPoint[]): ApiScheduleItem["bacnetBindings"] {
  return points.map((p) => ({
    id: p.id,
    pointId: p.id,
    name: p.name,
    objectId: p.objectId?.trim() || null,
  }));
}

export function profilesToDoc(
  profiles: ScheduleProfile[],
  meta: Pick<ApiScheduleDoc, "hostedScheduleName" | "timezone" | "version"> & {
    descriptionsById?: Record<string, string>;
    assignmentsById?: Record<string, string[]>;
  },
): ApiScheduleDoc {
  const schedules: ApiScheduleItem[] = profiles.map((p) => ({
    id: p.id,
    label: p.name,
    description: meta.descriptionsById?.[p.id] ?? "",
    assignments: meta.assignmentsById?.[p.id] ?? [],
    weekly: formToWeekly(p.form),
    holidays: holidaysToApi(p.holidays),
    bacnetBindings: pointsToBindings(p.bacnetPoints),
  }));
  return {
    version: meta.version ?? 2,
    timezone: meta.timezone ?? "local",
    hostedScheduleName: (meta.hostedScheduleName ?? "occupancy-schedule").trim() || "occupancy-schedule",
    schedules,
  };
}

export function extractMetaFromDoc(doc: ApiScheduleDoc): {
  hostedScheduleName: string;
  timezone: string;
  version: number;
  descriptionsById: Record<string, string>;
  assignmentsById: Record<string, string[]>;
} {
  const descriptionsById: Record<string, string> = {};
  const assignmentsById: Record<string, string[]> = {};
  for (const s of doc.schedules ?? []) {
    if (!s || typeof s !== "object") continue;
    const id = String((s as ApiScheduleItem).id ?? "");
    if (!id) continue;
    descriptionsById[id] = String((s as ApiScheduleItem).description ?? "");
    assignmentsById[id] = Array.isArray((s as ApiScheduleItem).assignments)
      ? ((s as ApiScheduleItem).assignments as string[]).map(String)
      : [];
  }
  return {
    hostedScheduleName: String(doc.hostedScheduleName ?? "occupancy-schedule"),
    timezone: String(doc.timezone ?? "local"),
    version: Number(doc.version ?? 2),
    descriptionsById,
    assignmentsById,
  };
}
