export type DayName =
  | 'Sunday'
  | 'Monday'
  | 'Tuesday'
  | 'Wednesday'
  | 'Thursday'
  | 'Friday'
  | 'Saturday';

export const DAYS: DayName[] = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];

/** Configurable BACnet / supervisory points assigned to a schedule profile */
export type BacnetPoint = {
  id: string;
  /** Human-readable label (e.g. AHU SAT) */
  name: string;
  /** Optional BACnet-style reference for integration (e.g. AV:1 or analog-value 1) */
  objectId?: string;
};

/** Per-day operating window (points live under BACnet). */
export type DayFormRow = {
  /** When true, this weekday has no run on the calendar (unoccupied / no schedule). */
  noSchedule: boolean;
  start: string;
  end: string;
};

export type WeekFormState = Record<DayName, DayFormRow>;

/** Named weekly run + BACnet points for that profile only */
export type ScheduleProfile = {
  id: string;
  name: string;
  form: WeekFormState;
  bacnetPoints: BacnetPoint[];
};

export type CalendarBlock = {
  id: string;
  day: DayName;
  start: string;
  end: string;
  label: string;
};

/** Whole-day holiday; unoccupied defaults to false until the user enables it */
export type HolidayEntry = {
  id: string;
  /** ISO date YYYY-MM-DD */
  date: string;
  unoccupied: boolean;
};

export const INITIAL_BACNET_POINTS: BacnetPoint[] = [
  { id: 'ahu', name: 'AHU supply air temp', objectId: 'AV:1' },
  { id: 'vav', name: 'VAV zone flow', objectId: 'AV:2' },
  { id: 'clg', name: 'Cooling setpoint', objectId: 'AV:3' },
  { id: 'htg', name: 'Heating setpoint', objectId: 'AV:4' },
  { id: 'fan', name: 'Supply fan command', objectId: 'BV:1' },
  { id: 'econ', name: 'Economizer enable', objectId: 'BV:2' },
];
