export type DayName =
  | "Sunday"
  | "Monday"
  | "Tuesday"
  | "Wednesday"
  | "Thursday"
  | "Friday"
  | "Saturday";

export const DAYS: DayName[] = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

export type BacnetBinding = {
  id: string;
  /** Supervisor point id from BAS Lite driver config */
  pointId: string;
  name: string;
  /** Optional BACnet object hint (metadata) */
  objectId?: string;
};

export type DayFormRow = {
  noSchedule: boolean;
  start: string;
  end: string;
};

export type WeekFormState = Record<DayName, DayFormRow>;

export type ScheduleProfile = {
  id: string;
  name: string;
  form: WeekFormState;
  bacnetBindings: BacnetBinding[];
};

export type CalendarBlock = {
  id: string;
  day: DayName;
  start: string;
  end: string;
  label: string;
};

export type HolidayEntry = {
  id: string;
  date: string;
  unoccupied: boolean;
};
