import type { BacnetBinding, CalendarBlock, WeekFormState } from "./scheduleTypes";
import { DAYS } from "./scheduleTypes";

export const timeToMinutes = (time: string): number => {
  const [h, m] = time.split(":").map(Number);
  return h * 60 + m;
};

export function cloneWeekForm(form: WeekFormState): WeekFormState {
  const next = {} as WeekFormState;
  for (const d of DAYS) {
    next[d] = { ...form[d] };
  }
  return next;
}

export function cloneBindings(points: BacnetBinding[]): BacnetBinding[] {
  return points.map((p) => ({ ...p }));
}

export function blocksFromOperatingWeek(form: WeekFormState, profileName: string): CalendarBlock[] {
  const out: CalendarBlock[] = [];
  for (const day of DAYS) {
    const row = form[day];
    if (row.noSchedule) continue;
    const startM = timeToMinutes(row.start);
    const endM = timeToMinutes(row.end);
    if (endM <= startM) continue;
    out.push({
      id: `${day}-run`,
      day,
      start: row.start,
      end: row.end,
      label: profileName,
    });
  }
  return out;
}
