import { Fragment, useMemo, useState, type CSSProperties } from "react";
import { BacnetPointsEditor } from "./components/BacnetPointsEditor";
import { HolidayCalendarSection } from "./components/HolidayCalendarSection";
import type { DayName, HolidayEntry, ScheduleProfile, WeekFormState } from "./shared/scheduleTypes";
import { DAYS } from "./shared/scheduleTypes";
import {
  blocksFromOperatingWeek,
  cloneBacnetPoints,
  cloneWeekForm,
  timeToMinutes,
} from "./shared/scheduleUtils";
import {
  docToProfiles,
  extractMetaFromDoc,
  profilesToDoc,
  type ApiScheduleDoc,
} from "./scheduleApiBridge";

const HOUR_ROW_PX = 40;
const HEADER_ROW_PX = HOUR_ROW_PX;
const HOURS = 24;
const GRID_ROWS = 1 + HOURS;

function getBlockStyle(block: { day: DayName; start: string; end: string }): CSSProperties {
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

type Props = {
  initialDoc: ApiScheduleDoc;
  onSave: (doc: ApiScheduleDoc) => Promise<void>;
  onAfterSave?: () => void;
};

export function ScheduleIslandApp({ initialDoc, onSave, onAfterSave }: Props) {
  const meta0 = useMemo(() => extractMetaFromDoc(initialDoc), [initialDoc]);
  const initProfiles = useMemo(() => docToProfiles(initialDoc), [initialDoc]);

  const [schedules, setSchedules] = useState<ScheduleProfile[]>(initProfiles);
  const [activeScheduleId, setActiveScheduleId] = useState(initProfiles[0]?.id ?? "");
  const [newProfileName, setNewProfileName] = useState("");
  const [hostedScheduleName, setHostedScheduleName] = useState(meta0.hostedScheduleName);
  const [timezone] = useState(meta0.timezone);
  const [version] = useState(meta0.version);
  const [descriptionsById] = useState(meta0.descriptionsById);
  const [assignmentsById, setAssignmentsById] = useState(meta0.assignmentsById);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  const activeProfile = useMemo(() => {
    const found = schedules.find((s) => s.id === activeScheduleId) ?? schedules[0];
    if (!found) {
      throw new Error("Invariant: at least one schedule profile is required");
    }
    return found;
  }, [schedules, activeScheduleId]);

  const form = activeProfile.form;
  const bacnetPoints = activeProfile.bacnetPoints;
  const holidays = activeProfile.holidays;

  const assignmentsCsv = (assignmentsById[activeScheduleId] ?? []).join(", ");

  function setAssignmentsCsv(csv: string) {
    const parts = csv
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    setAssignmentsById((prev) => ({ ...prev, [activeScheduleId]: parts }));
  }

  function handleBacnetPointsChange(next: typeof bacnetPoints) {
    setSchedules((prev) => prev.map((s) => (s.id === activeScheduleId ? { ...s, bacnetPoints: next } : s)));
  }

  function handleHolidaysChange(next: HolidayEntry[]) {
    setSchedules((prev) => prev.map((s) => (s.id === activeScheduleId ? { ...s, holidays: next } : s)));
  }

  const blocks = useMemo(
    () => blocksFromOperatingWeek(form, activeProfile.name),
    [form, activeProfile.name],
  );

  function updateActiveForm(updater: (prev: WeekFormState) => WeekFormState) {
    setSchedules((prev) =>
      prev.map((s) => (s.id === activeScheduleId ? { ...s, form: updater(s.form) } : s)),
    );
  }

  function updateDay(day: DayName, field: "start" | "end" | "noSchedule", value: string | boolean) {
    updateActiveForm((prev) => ({
      ...prev,
      [day]: { ...prev[day], [field]: value },
    }));
  }

  function addProfile() {
    const name = newProfileName.trim() || `Profile ${schedules.length + 1}`;
    const sid = crypto.randomUUID();
    setSchedules((prev) => [
      ...prev,
      {
        id: sid,
        name,
        form: cloneWeekForm(activeProfile.form),
        bacnetPoints: cloneBacnetPoints(activeProfile.bacnetPoints),
        holidays: activeProfile.holidays.map((h) => ({ ...h, id: crypto.randomUUID() })),
      },
    ]);
    setAssignmentsById((prev) => ({ ...prev, [sid]: [...(prev[activeScheduleId] ?? [])] }));
    setActiveScheduleId(sid);
    setNewProfileName("");
  }

  function deleteActiveProfile() {
    if (schedules.length <= 1) return;
    const filtered = schedules.filter((s) => s.id !== activeScheduleId);
    setSchedules(filtered);
    setActiveScheduleId(filtered[0].id);
  }

  function moveActiveToFirst() {
    setSchedules((prev) => {
      const i = prev.findIndex((s) => s.id === activeScheduleId);
      if (i <= 0) return prev;
      const copy = [...prev];
      const [x] = copy.splice(i, 1);
      copy.unshift(x);
      return copy;
    });
  }

  async function handleSave() {
    setSaving(true);
    setSaveMsg(null);
    setSaveErr(null);
    try {
      const doc = profilesToDoc(schedules, {
        hostedScheduleName,
        timezone,
        version,
        descriptionsById,
        assignmentsById,
      });
      await onSave(doc);
      setSaveMsg("Saved to supervisor.");
      onAfterSave?.();
    } catch (e) {
      setSaveErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bas-schedule-island">
      <div className="layout">
        <div className="schedule-save-bar">
          <button type="button" className="btn primary" disabled={saving} onClick={() => void handleSave()}>
            {saving ? "Saving…" : "Save to supervisor"}
          </button>
          {saveMsg ? <span className="schedule-save-msg">{saveMsg}</span> : null}
          {saveErr ? <span className="schedule-save-msg error">{saveErr}</span> : null}
        </div>

        <header className="page-header">
          <h1>Weekly equipment schedule</h1>
          <p className="lede">
            Schedules, operating week, holidays, and BACnet point metadata are stored in{" "}
            <code className="rounded bg-muted px-1">schedule.json</code>. The{" "}
            <strong>first schedule in the list</strong> is what the API pushes to the hosted BACnet weekly table.
          </p>
        </header>

        <section className="panel profile-panel" aria-labelledby="profile-heading">
          <h2 id="profile-heading">Schedule</h2>
          <p className="section-hint">
            Choose which schedule is active in the editor. The calendar and operating week reflect that selection.
            Device assignments (comma-separated device IDs) determine effective occupancy per device on the summary
            below the editor.
          </p>
          <div className="hosted-name-row">
            <label htmlFor="hosted-schedule-name">Hosted BACnet schedule name</label>
            <input
              id="hosted-schedule-name"
              className="control"
              value={hostedScheduleName}
              onChange={(e) => setHostedScheduleName(e.target.value)}
              aria-label="Hosted BACnet schedule name"
            />
          </div>
          <div className="hosted-name-row">
            <label htmlFor="assignments-csv">Device IDs for this schedule</label>
            <input
              id="assignments-csv"
              className="control"
              value={assignmentsCsv}
              onChange={(e) => setAssignmentsCsv(e.target.value)}
              placeholder="device-1, device-2"
              aria-label="Comma-separated device IDs assigned to this schedule"
            />
          </div>
          <div className="profile-toolbar">
            <label className="profile-select-label" htmlFor="profile-select">
              Select schedule
            </label>
            <select
              id="profile-select"
              className="control profile-select"
              value={activeScheduleId}
              onChange={(e) => setActiveScheduleId(e.target.value)}
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
                onChange={(e) => setNewProfileName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addProfile()}
                aria-label="Name for new schedule"
              />
              <button type="button" className="btn primary" onClick={addProfile}>
                Add schedule
              </button>
            </div>
            <button type="button" className="btn" onClick={moveActiveToFirst} disabled={schedules[0]?.id === activeScheduleId}>
              Move active to first (BACnet)
            </button>
            <button
              type="button"
              className="btn danger"
              disabled={schedules.length <= 1}
              title={schedules.length <= 1 ? "Keep at least one schedule" : "Delete the active schedule"}
              onClick={deleteActiveProfile}
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
            Schedule: <strong>{activeProfile.name}</strong> — days with <strong>No schedule</strong> unchecked show their
            start–stop window below.
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
            For <strong>{activeProfile.name}</strong>: check <strong>No schedule</strong> on a day to treat it as off /
            unoccupied (it will not appear on the calendar). Uncheck to set start and stop for that day.
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

        <HolidayCalendarSection holidays={holidays} onChange={handleHolidaysChange} />

        <BacnetPointsEditor points={bacnetPoints} onChange={handleBacnetPointsChange} profileName={activeProfile.name} />
      </div>
    </div>
  );
}
