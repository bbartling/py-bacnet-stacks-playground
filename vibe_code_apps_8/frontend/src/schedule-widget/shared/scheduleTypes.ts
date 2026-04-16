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

export type BacnetPoint = {
  id: string;
  name: string;
  objectId?: string;
};

export type DayFormRow = {
  noSchedule: boolean;
  start: string;
  end: string;
};

export type WeekFormState = Record<DayName, DayFormRow>;

export type HolidayEntry = {
  id: string;
  date: string;
  unoccupied: boolean;
};

/** Named weekly run + BACnet points + holidays for that profile (matches API schedule item). */
export type ScheduleProfile = {
  id: string;
  name: string;
  form: WeekFormState;
  bacnetPoints: BacnetPoint[];
  holidays: HolidayEntry[];
};

export type CalendarBlock = {
  id: string;
  day: DayName;
  start: string;
  end: string;
  label: string;
};

export const INITIAL_BACNET_POINTS: BacnetPoint[] = [
  { id: "ahu", name: "AHU supply air temp", objectId: "AV:1" },
  { id: "vav", name: "VAV zone flow", objectId: "AV:2" },
  { id: "clg", name: "Cooling setpoint", objectId: "AV:3" },
  { id: "htg", name: "Heating setpoint", objectId: "AV:4" },
  { id: "fan", name: "Supply fan command", objectId: "BV:1" },
  { id: "econ", name: "Economizer enable", objectId: "BV:2" },
];
