import { Fragment, useMemo, type CSSProperties } from "react";
import { HolidayCalendarSection } from "./HolidayCalendarSection";
import { ScheduleBindingsEditor } from "./ScheduleBindingsEditor";
import type { HolidayEntry, ScheduleProfile, WeekFormState } from "./scheduleTypes";
import { DAYS } from "./scheduleTypes";
import { blocksFromOperatingWeek, timeToMinutes } from "./scheduleUtils";

const HOUR_ROW_PX = 40;
const HEADER_ROW_PX = HOUR_ROW_PX;
const HOURS = 24;
const GRID_ROWS = 1 + HOURS;

function getBlockStyle(block: { day: (typeof DAYS)[number]; start: string; end: string }): CSSProperties {
  const dayIndex = DAYS.indexOf(block.day);
  const topMinutes = timeToMinutes(block.start);
  const endMinutes = timeToMinutes(block.end);
  const bodyTopPx = (topMinutes / (HOURS * 60)) * HOURS * HOUR_ROW_PX;
  const heightPx = ((endMinutes - topMinutes) / 60) * HOUR_ROW_PX;
  return {
    left: `calc(80px + (100% - 80px) * ${dayIndex} / 7)`,
    width: `calc((100% - 80px) / 7 - 2px)`,
    top: `${HEADER_ROW_PX + bodyTopPx}px`,
    height: `${heightPx}px`,
  };
}

export type PointOpt = { id: string; deviceId: string; label: string; name: string };

export type ScheduleWidgetBodyProps = {
  schedules: ScheduleProfile[];
  activeScheduleId: string;
  onSelectSchedule: (id: string) => void;
  newProfileName: string;
  onNewProfileName: (v: string) => void;
  onAddProfile: () => void;
  onDeleteActiveProfile: () => void;
  onUpdateActiveForm: (updater: (prev: WeekFormState) => WeekFormState) => void;
  onBindingsChange: (next: ScheduleProfile["bacnetBindings"]) => void;
  holidays: HolidayEntry[];
  onHolidaysChange: (h: HolidayEntry[]) => void;
  points: PointOpt[];
};

export function ScheduleWidgetBody({
  schedules,
  activeScheduleId,
  onSelectSchedule,
  newProfileName,
  onNewProfileName,
  onAddProfile,
  onDeleteActiveProfile,
  onUpdateActiveForm,
  onBindingsChange,
  holidays,
  onHolidaysChange,
  points,
}: ScheduleWidgetBodyProps) {
  const activeProfile = useMemo(() => {
    const found = schedules.find((s) => s.id === activeScheduleId) ?? schedules[0];
    if (!found) throw new Error("ScheduleWidgetBody requires at least one profile");
    return found;
  }, [schedules, activeScheduleId]);

  const form = activeProfile.form;
  const bacnetBindings = activeProfile.bacnetBindings;

  function updateDay(day: (typeof DAYS)[number], field: "start" | "end" | "noSchedule", value: string | boolean) {
    onUpdateActiveForm((prev) => ({
      ...prev,
      [day]: { ...prev[day], [field]: value },
    }));
  }

  const blocks = useMemo(() => blocksFromOperatingWeek(form, activeProfile.name), [form, activeProfile.name]);

  return (
    <>
      <header className="page-header">
        <h1>Weekly equipment schedule</h1>
        <p className="lede">
          Visual week grid, operating times, holidays, and supervisor point bindings. Save from the bar above to persist
          and push the BACnet hosted schedule.
        </p>
      </header>

      <section className="panel profile-panel" aria-labelledby="profile-heading">
        <h2 id="profile-heading">Schedule</h2>
        <p className="section-hint">Choose which schedule is active. The calendar and operating week follow that selection.</p>
        <div className="profile-toolbar">
          <label className="profile-select-label" htmlFor="profile-select">
            Select schedule
          </label>
          <select
            id="profile-select"
            className="control profile-select"
            value={activeScheduleId}
            onChange={(e) => onSelectSchedule(e.target.value)}
          >
            {schedules.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <div className="profile-add">
            <input
              className="control"
              placeholder="New schedule name"
              value={newProfileName}
              onChange={(e) => onNewProfileName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onAddProfile()}
              aria-label="Name for new schedule"
            />
            <button type="button" className="btn primary" onClick={onAddProfile}>
              Add schedule
            </button>
          </div>
          <button
            type="button"
            className="btn danger"
            disabled={schedules.length <= 1}
            title={schedules.length <= 1 ? "Keep at least one schedule" : "Delete the active schedule"}
            onClick={onDeleteActiveProfile}
          >
            Delete active schedule
          </button>
        </div>
      </section>

      <section className="panel calendar-panel" aria-labelledby="cal-heading">
        <div className="calendar-head">
          <h2 id="cal-heading">Weekly calendar</h2>
          <span className="badge-readonly" title="Driven by the selected schedule">
            Read-only
          </span>
        </div>
        <p className="calendar-hint">
          Schedule: <strong>{activeProfile.name}</strong> — days with <strong>No schedule</strong> checked are off and
          do not draw a block.
        </p>
        <div
          className="schedule-grid"
          style={{
            position: "relative",
            height: GRID_ROWS * HOUR_ROW_PX,
          }}
          role="img"
          aria-label={`Weekly operating hours for ${activeProfile.name}`}
        >
          <div style={{ gridRow: 1, gridColumn: 1 }} />
          {DAYS.map((day) => (
            <div key={day} className="day-header">
              {day.slice(0, 3)}
            </div>
          ))}
          {Array.from({ length: 24 }, (_, hr) => (
            <Fragment key={hr}>
              <div className="time-label">{hr.toString().padStart(2, "0")}:00</div>
              {DAYS.map((day) => (
                <div key={`${day}-${hr}`} />
              ))}
            </Fragment>
          ))}
          {blocks.map((block) => (
            <div
              key={`${activeScheduleId}-${block.id}`}
              className="event-block"
              style={getBlockStyle(block)}
              title={`${activeProfile.name} · ${block.day} ${block.start}–${block.end}`}
            >
              <span className="event-label">{block.label}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel form-panel" aria-labelledby="form-heading">
        <h2 id="form-heading">Operating week</h2>
        <p className="section-hint">
          For <strong>{activeProfile.name}</strong>: check <strong>No schedule</strong> on a day for unoccupied (no
          calendar block). Uncheck to set start and stop.
        </p>
        <div className="form-table" role="table">
          <div className="form-row form-row-head" role="row">
            <span role="columnheader">Day</span>
            <span role="columnheader" title="No schedule / unoccupied this weekday">
              Off
            </span>
            <span role="columnheader">Start</span>
            <span role="columnheader">Stop</span>
          </div>
          {DAYS.map((day) => (
            <div
              key={day}
              className={`form-row${form[day].noSchedule ? " form-row-muted" : ""}`}
              role="row"
            >
              <span className="day-cell" role="rowheader">
                {day}
              </span>
              <label className="form-off-cell" title="No run this day (unoccupied)">
                <input
                  type="checkbox"
                  checked={form[day].noSchedule}
                  onChange={(e) => updateDay(day, "noSchedule", e.target.checked)}
                />
                <span className="form-off-label">No schedule</span>
              </label>
              <label className="sr-only" htmlFor={`start-${day}`}>
                Start time {day}
              </label>
              <input
                id={`start-${day}`}
                className="control time"
                type="time"
                value={form[day].start}
                disabled={form[day].noSchedule}
                onChange={(e) => updateDay(day, "start", e.target.value)}
              />
              <label className="sr-only" htmlFor={`end-${day}`}>
                Stop time {day}
              </label>
              <input
                id={`end-${day}`}
                className="control time"
                type="time"
                value={form[day].end}
                disabled={form[day].noSchedule}
                onChange={(e) => updateDay(day, "end", e.target.value)}
              />
            </div>
          ))}
        </div>
      </section>

      <HolidayCalendarSection holidays={holidays} onChange={onHolidaysChange} />

      <ScheduleBindingsEditor
        bindings={bacnetBindings}
        onChange={onBindingsChange}
        profileName={activeProfile.name}
        points={points}
      />
    </>
  );
}
