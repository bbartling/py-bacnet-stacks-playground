import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { apiFetch } from "@/lib/bas-fetch";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
type DayKey = (typeof DAYS)[number];

type DayBlock = { occupied: boolean; startMinutes: number; endMinutes: number };
type Holiday = { start: string; end: string; allDay: boolean; occupied: boolean };
type Linked = { deviceId: string; pointName: string; note?: string };

type ScheduleDoc = {
  version: number;
  label?: string;
  weekly: Record<DayKey, DayBlock>;
  holidays: Holiday[];
  linkedPoints: Linked[];
};

function minutesToLabel(m: number): string {
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${String(h).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

export function BasSchedulePage() {
  const qc = useQueryClient();
  const [doc, setDoc] = useState<ScheduleDoc | null>(null);

  const loaded = useQuery({
    queryKey: ["bas-schedule"],
    queryFn: () => apiFetch<ScheduleDoc>("api/schedule"),
  });

  useEffect(() => {
    if (loaded.data) {
      setDoc((prev) => prev ?? structuredClone(loaded.data!));
    }
  }, [loaded.data]);

  const save = useMutation({
    mutationFn: async (body: ScheduleDoc) =>
      apiFetch("api/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bas-schedule"] }),
  });

  const points = useQuery({
    queryKey: ["bas-points"],
    queryFn: () => apiFetch<{ items: { deviceId: string; name: string; label: string }[] }>("api/points"),
  });

  const working = doc ?? loaded.data;
  if (!working) {
    return <p className="text-sm text-muted-foreground">Loading schedule…</p>;
  }

  const setDay = (d: DayKey, patch: Partial<DayBlock>) => {
    setDoc({
      ...working,
      weekly: { ...working.weekly, [d]: { ...working.weekly[d], ...patch } },
    });
  };

  const addHoliday = () => {
    const today = new Date().toISOString().slice(0, 10);
    setDoc({
      ...working,
      holidays: [...working.holidays, { start: today, end: today, allDay: true, occupied: false }],
    });
  };

  const updateHoliday = (i: number, h: Partial<Holiday>) => {
    const next = [...working.holidays];
    next[i] = { ...next[i], ...h };
    setDoc({ ...working, holidays: next });
  };

  const removeHoliday = (i: number) => {
    setDoc({ ...working, holidays: working.holidays.filter((_, j) => j !== i) });
  };

  const addLink = () => {
    const first = points.data?.items[0];
    setDoc({
      ...working,
      linkedPoints: [
        ...working.linkedPoints,
        { deviceId: first?.deviceId ?? "", pointName: first?.name ?? "", note: "" },
      ],
    });
  };

  const updateLink = (i: number, p: Partial<Linked>) => {
    const next = [...working.linkedPoints];
    next[i] = { ...next[i], ...p };
    setDoc({ ...working, linkedPoints: next });
  };

  const removeLink = (i: number) => {
    setDoc({ ...working, linkedPoints: working.linkedPoints.filter((_, j) => j !== i) });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Occupancy schedule</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          One occupied window per weekday (minutes from midnight). Holidays override with whole-day or
          date ranges. Linked points record which BACnet outputs this schedule should drive (wire in agent
          logic later).
        </p>
      </div>

      <Card>
        <CardContent className="space-y-6 pt-6">
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm">
              Label{" "}
              <input
                className="ml-2 w-56 rounded border border-border bg-background px-2 py-1 text-sm"
                value={working.label ?? ""}
                onChange={(e) => setDoc({ ...working, label: e.target.value })}
              />
            </label>
            <button
              type="button"
              className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              onClick={() => save.mutate(working)}
              disabled={save.isPending}
            >
              Save schedule
            </button>
          </div>

          <div className="space-y-5">
            {DAYS.map((d) => {
              const row = working.weekly[d];
              return (
                <div key={d} className="grid gap-3 border-b border-border/60 pb-4 sm:grid-cols-12">
                  <div className="font-medium capitalize sm:col-span-2">{d}</div>
                  <label className="flex items-center gap-2 text-sm sm:col-span-2">
                    <input
                      type="checkbox"
                      checked={row.occupied}
                      onChange={(e) => setDay(d, { occupied: e.target.checked })}
                    />
                    Occupied
                  </label>
                  <div className="sm:col-span-8 space-y-1">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Start {minutesToLabel(row.startMinutes)}</span>
                      <span>End {minutesToLabel(row.endMinutes)}</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={24 * 60}
                      value={row.startMinutes}
                      disabled={!row.occupied}
                      onChange={(e) =>
                        setDay(d, {
                          startMinutes: Number(e.target.value),
                          endMinutes: Math.max(row.endMinutes, Number(e.target.value) + 30),
                        })
                      }
                      className="w-full"
                    />
                    <input
                      type="range"
                      min={0}
                      max={24 * 60}
                      value={row.endMinutes}
                      disabled={!row.occupied}
                      onChange={(e) =>
                        setDay(d, {
                          endMinutes: Number(e.target.value),
                          startMinutes: Math.min(row.startMinutes, Number(e.target.value) - 30),
                        })
                      }
                      className="w-full"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Holidays / overrides</h2>
            <button type="button" className="text-xs text-primary hover:underline" onClick={addHoliday}>
              Add range
            </button>
          </div>
          <ul className="space-y-2">
            {working.holidays.map((h, i) => (
              <li key={i} className="flex flex-wrap items-end gap-2 rounded-md border border-border/60 p-2">
                <label className="text-xs">
                  From
                  <input
                    type="date"
                    className="ml-1 rounded border border-border bg-background px-1 py-0.5"
                    value={h.start}
                    onChange={(e) => updateHoliday(i, { start: e.target.value })}
                  />
                </label>
                <label className="text-xs">
                  To
                  <input
                    type="date"
                    className="ml-1 rounded border border-border bg-background px-1 py-0.5"
                    value={h.end}
                    onChange={(e) => updateHoliday(i, { end: e.target.value })}
                  />
                </label>
                <label className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={h.allDay}
                    onChange={(e) => updateHoliday(i, { allDay: e.target.checked })}
                  />
                  All day
                </label>
                <label className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={h.occupied}
                    onChange={(e) => updateHoliday(i, { occupied: e.target.checked })}
                  />
                  Occupied override
                </label>
                <button type="button" className="text-xs text-destructive" onClick={() => removeHoliday(i)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Linked BACnet points</h2>
            <button type="button" className="text-xs text-primary hover:underline" onClick={addLink}>
              Add row
            </button>
          </div>
          <ul className="space-y-2">
            {working.linkedPoints.map((lp, i) => (
              <li key={i} className="flex flex-wrap gap-2 rounded-md border border-border/60 p-2 text-sm">
                <select
                  className="rounded border border-border bg-background px-2 py-1 text-xs"
                  value={`${lp.deviceId}::${lp.pointName}`}
                  onChange={(e) => {
                    const [deviceId, pointName] = e.target.value.split("::");
                    updateLink(i, { deviceId, pointName });
                  }}
                >
                  {(points.data?.items ?? []).map((p) => (
                    <option key={p.deviceId + p.name} value={`${p.deviceId}::${p.name}`}>
                      {p.deviceId} · {p.label} ({p.name})
                    </option>
                  ))}
                </select>
                <input
                  className="min-w-[160px] flex-1 rounded border border-border bg-background px-2 py-1 text-xs"
                  placeholder="Note"
                  value={lp.note ?? ""}
                  onChange={(e) => updateLink(i, { note: e.target.value })}
                />
                <button type="button" className="text-xs text-destructive" onClick={() => removeLink(i)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
