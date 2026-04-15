import { eachDayOfInterval, format, parse } from "date-fns";
import { useMemo, useState } from "react";
import { DayPicker, type DateRange } from "react-day-picker";
import type { HolidayEntry } from "./scheduleTypes";
import "react-day-picker/style.css";

type Props = {
  holidays: HolidayEntry[];
  onChange: (holidays: HolidayEntry[]) => void;
};

type PickerMode = "multiple" | "range";

function mergeNewHolidayDates(existing: HolidayEntry[], dates: Date[]): HolidayEntry[] {
  const next = [...existing];
  const seen = new Set(next.map((h) => h.date));
  for (const d of dates) {
    const dateStr = format(d, "yyyy-MM-dd");
    if (seen.has(dateStr)) continue;
    seen.add(dateStr);
    next.push({
      id: crypto.randomUUID(),
      date: dateStr,
      unoccupied: false,
    });
  }
  next.sort((a, b) => a.date.localeCompare(b.date));
  return next;
}

export function HolidayCalendarSection({ holidays, onChange }: Props) {
  const [pickerMode, setPickerMode] = useState<PickerMode>("multiple");
  const [pickerDates, setPickerDates] = useState<Date[] | undefined>();
  const [range, setRange] = useState<DateRange | undefined>();

  const modifiers = useMemo(() => {
    const dates = holidays.map((h) => parse(h.date, "yyyy-MM-dd", new Date()));
    return { alreadyHoliday: dates };
  }, [holidays]);

  function setMode(mode: PickerMode) {
    setPickerMode(mode);
    setPickerDates(undefined);
    setRange(undefined);
  }

  function addMultipleToHolidays() {
    if (!pickerDates?.length) return;
    onChange(mergeNewHolidayDates(holidays, pickerDates));
    setPickerDates(undefined);
  }

  function addRangeToHolidays() {
    if (!range?.from) return;
    const a = range.from;
    const b = range.to ?? a;
    const start = a <= b ? a : b;
    const end = a <= b ? b : a;
    const days = eachDayOfInterval({ start, end });
    onChange(mergeNewHolidayDates(holidays, days));
    setRange(undefined);
  }

  function removeHoliday(id: string) {
    onChange(holidays.filter((h) => h.id !== id));
  }

  function setUnoccupied(id: string, value: boolean) {
    onChange(holidays.map((h) => (h.id === id ? { ...h, unoccupied: value } : h)));
  }

  const rangeReady = Boolean(range?.from && range?.to);
  const rangePartial = Boolean(range?.from && !range?.to);

  return (
    <section className="panel holiday-panel" aria-labelledby="holiday-heading">
      <h2 id="holiday-heading">Holiday calendar</h2>
      <p className="section-hint">
        <strong>Individual dates:</strong> tap days (multi-select), then add.
        <strong> Date range:</strong> click the start day, then the end day, then add. New entries default with{" "}
        <strong>Unoccupied</strong> unchecked; use Delete to remove.
      </p>

      <div className="holiday-mode-toggle" role="group" aria-label="Holiday selection mode">
        <button
          type="button"
          className={`btn mode-btn ${pickerMode === "multiple" ? "active" : ""}`}
          onClick={() => setMode("multiple")}
        >
          Individual dates
        </button>
        <button
          type="button"
          className={`btn mode-btn ${pickerMode === "range" ? "active" : ""}`}
          onClick={() => setMode("range")}
        >
          Date range
        </button>
      </div>

      <div className="holiday-layout">
        <div className="holiday-picker-wrap">
          {pickerMode === "multiple" ? (
            <DayPicker
              mode="multiple"
              selected={pickerDates}
              onSelect={setPickerDates}
              modifiers={modifiers}
              modifiersClassNames={{
                alreadyHoliday: "rdp-day_already-holiday",
              }}
              showOutsideDays
              fixedWeeks
            />
          ) : (
            <DayPicker
              mode="range"
              selected={range}
              onSelect={setRange}
              modifiers={modifiers}
              modifiersClassNames={{
                alreadyHoliday: "rdp-day_already-holiday",
              }}
              showOutsideDays
              fixedWeeks
            />
          )}

          {pickerMode === "multiple" ? (
            <button type="button" className="btn primary holiday-add-btn" onClick={addMultipleToHolidays} disabled={!pickerDates?.length}>
              Add selected dates as holidays
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn primary holiday-add-btn"
                onClick={addRangeToHolidays}
                disabled={!range?.from}
                title={
                  rangePartial ? "Pick the end day to complete the range (or add a single day)" : undefined
                }
              >
                {rangePartial
                  ? "Add this day (pick end for a range)"
                  : rangeReady
                    ? "Add range as holidays"
                    : "Select start date on the calendar"}
              </button>
              {rangePartial ? (
                <p className="holiday-range-hint">
                  Second click sets the end of the range. Or use the button above to add just the first day.
                </p>
              ) : null}
            </>
          )}

          <p className="holiday-legend">
            <span className="legend-swatch already" /> Already a holiday
          </p>
        </div>
        <div className="holiday-list-wrap">
          <h3 className="holiday-list-title">Holiday list</h3>
          {holidays.length === 0 ? (
            <p className="holiday-empty">No holidays configured.</p>
          ) : (
            <ul className="holiday-list">
              {holidays.map((h) => (
                <li key={h.id} className="holiday-list-item">
                  <span className="holiday-date">
                    {format(parse(h.date, "yyyy-MM-dd", new Date()), "PPP")}
                    <span className="holiday-iso">({h.date})</span>
                  </span>
                  <label className="holiday-occ">
                    <input type="checkbox" checked={h.unoccupied} onChange={(e) => setUnoccupied(h.id, e.target.checked)} />
                    Unoccupied
                  </label>
                  <button type="button" className="btn danger btn-sm" onClick={() => removeHoliday(h.id)}>
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
