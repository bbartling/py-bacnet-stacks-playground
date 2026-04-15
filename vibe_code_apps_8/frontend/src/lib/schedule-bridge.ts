import type { BacnetBinding, DayName, HolidayEntry, ScheduleProfile, WeekFormState } from "@/components/schedule-widget/scheduleTypes";
import { DAYS } from "@/components/schedule-widget/scheduleTypes";

export type BackendDayKey = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";

type DayBlock = { occupied: boolean; startMinutes: number; endMinutes: number };

export type ScheduleItemBridge = {
  id: string;
  label: string;
  description?: string;
  assignments: string[];
  weekly: Record<BackendDayKey, DayBlock>;
  holidays: { date?: string; start?: string; end?: string; occupied: boolean }[];
  bacnetBindings?: BacnetBinding[];
};

export type ScheduleDocBridge = {
  version: number;
  timezone?: string;
  hostedScheduleName?: string;
  schedules: ScheduleItemBridge[];
};

const DEMO_TO_BACKEND: Record<DayName, BackendDayKey> = {
  Sunday: "sun",
  Monday: "mon",
  Tuesday: "tue",
  Wednesday: "wed",
  Thursday: "thu",
  Friday: "fri",
  Saturday: "sat",
};

function minutesToTime(m: number): string {
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${String(h).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

export function defaultWeekForm(): WeekFormState {
  const run = (): WeekFormState["Monday"] => ({
    noSchedule: false,
    start: "08:00",
    end: "17:00",
  });
  const off = (): WeekFormState["Monday"] => ({
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

export function scheduleItemToProfile(item: ScheduleItemBridge): ScheduleProfile {
  const form = defaultWeekForm();
  for (const day of DAYS) {
    const bk = DEMO_TO_BACKEND[day];
    const row = item.weekly[bk];
    if (!row) continue;
    form[day] = {
      noSchedule: !row.occupied,
      start: minutesToTime(row.startMinutes),
      end: minutesToTime(row.endMinutes),
    };
  }
  const bindings = (item.bacnetBindings ?? []).map((b) => ({
    ...b,
    id: b.id || b.pointId || crypto.randomUUID(),
  }));
  return {
    id: item.id,
    name: item.label,
    form,
    bacnetBindings: bindings.length ? bindings : [],
  };
}

export function profileToWeekly(form: WeekFormState): Record<BackendDayKey, DayBlock> {
  const weekly = {} as Record<BackendDayKey, DayBlock>;
  for (const day of DAYS) {
    const bk = DEMO_TO_BACKEND[day];
    const row = form[day];
    if (row.noSchedule) {
      weekly[bk] = { occupied: false, startMinutes: 8 * 60, endMinutes: 17 * 60 };
    } else {
      const [sh, sm] = row.start.split(":").map(Number);
      const [eh, em] = row.end.split(":").map(Number);
      weekly[bk] = {
        occupied: true,
        startMinutes: sh * 60 + sm,
        endMinutes: eh * 60 + em,
      };
    }
  }
  return weekly;
}

export function holidaysToEntries(
  holidays: ScheduleItemBridge["holidays"],
): HolidayEntry[] {
  const out: HolidayEntry[] = [];
  let i = 0;
  for (const h of holidays) {
    if (h.date) {
      out.push({
        id: `hol-${h.date}-${i++}`,
        date: String(h.date),
        unoccupied: !h.occupied,
      });
    } else if (h.start) {
      const start = String(h.start);
      const end = String(h.end || h.start);
      const startD = new Date(start + "T12:00:00");
      const endD = new Date(end + "T12:00:00");
      for (let d = new Date(startD); d <= endD; d.setDate(d.getDate() + 1)) {
        const iso = d.toISOString().slice(0, 10);
        out.push({
          id: `hol-${iso}-${i++}`,
          date: iso,
          unoccupied: !h.occupied,
        });
      }
    }
  }
  out.sort((a, b) => a.date.localeCompare(b.date));
  return out;
}

export function entriesToHolidays(entries: HolidayEntry[]): ScheduleItemBridge["holidays"] {
  return entries.map((e) => ({
    date: e.date,
    occupied: !e.unoccupied,
  }));
}

export function mergeProfileIntoItem(
  item: ScheduleItemBridge,
  profile: ScheduleProfile,
  holidays: HolidayEntry[],
): ScheduleItemBridge {
  return {
    ...item,
    id: profile.id,
    label: profile.name,
    weekly: profileToWeekly(profile.form),
    holidays: entriesToHolidays(holidays),
    bacnetBindings: profile.bacnetBindings,
  };
}

export function parseScheduleAiJson(text: string): ScheduleDocBridge {
  const raw = JSON.parse(text) as unknown;
  if (!raw || typeof raw !== "object") throw new Error("JSON must be an object");
  const o = raw as Record<string, unknown>;
  if (!Array.isArray(o.schedules)) throw new Error("Missing schedules[]");
  return raw as ScheduleDocBridge;
}
