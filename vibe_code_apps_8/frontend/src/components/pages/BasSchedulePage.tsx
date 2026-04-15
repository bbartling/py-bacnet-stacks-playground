import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { apiFetch } from "@/lib/bas-fetch";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
type DayKey = (typeof DAYS)[number];

type DayBlock = { occupied: boolean; startMinutes: number; endMinutes: number };
type Holiday = { date?: string; start?: string; end?: string; occupied: boolean };
type ScheduleItem = {
  id: string;
  label: string;
  description?: string;
  assignments: string[];
  weekly: Record<DayKey, DayBlock>;
  holidays: Holiday[];
};
type ScheduleDoc = { version: number; timezone?: string; schedules: ScheduleItem[] };
type Effective = {
  localTime: string;
  devices: { deviceId: string; deviceName: string; occupied: boolean; reason: string }[];
};

function minutesToLabel(m: number): string {
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${String(h).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

function defaultSchedule(id: string, label: string): ScheduleItem {
  return {
    id,
    label,
    description: "",
    assignments: [],
    weekly: {
      mon: { occupied: true, startMinutes: 8 * 60, endMinutes: 17 * 60 },
      tue: { occupied: true, startMinutes: 8 * 60, endMinutes: 17 * 60 },
      wed: { occupied: true, startMinutes: 8 * 60, endMinutes: 17 * 60 },
      thu: { occupied: true, startMinutes: 8 * 60, endMinutes: 17 * 60 },
      fri: { occupied: true, startMinutes: 8 * 60, endMinutes: 17 * 60 },
      sat: { occupied: false, startMinutes: 8 * 60, endMinutes: 17 * 60 },
      sun: { occupied: false, startMinutes: 8 * 60, endMinutes: 17 * 60 },
    },
    holidays: [],
  };
}

function holidayMode(h: Holiday): "single" | "range" {
  return h.date ? "single" : "range";
}

export function BasSchedulePage() {
  const qc = useQueryClient();
  const [doc, setDoc] = useState<ScheduleDoc | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [syncNote, setSyncNote] = useState<string>("");

  const loaded = useQuery({
    queryKey: ["bas-schedule"],
    queryFn: () => apiFetch<ScheduleDoc>("api/schedule"),
  });

  useEffect(() => {
    if (loaded.data) {
      setDoc((prev) => prev ?? structuredClone(loaded.data!));
      setSelectedId((prev) => prev || loaded.data!.schedules?.[0]?.id || "");
    }
  }, [loaded.data]);

  const save = useMutation({
    mutationFn: async (body: ScheduleDoc) =>
      apiFetch<{ status: string; bacnetScheduleSync?: { ok?: boolean; message?: string; scheduleName?: string } }>("api/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bas-schedule"] });
      qc.invalidateQueries({ queryKey: ["bas-schedule-effective"] });
    },
  });

  const points = useQuery({
    queryKey: ["bas-points"],
    queryFn: () => apiFetch<{ items: { deviceId: string; name: string; label: string }[] }>("api/points"),
  });
  const devices = useQuery({
    queryKey: ["bas-devices"],
    queryFn: () => apiFetch<{ items: { id: string; displayName: string }[] }>("api/devices"),
    staleTime: 20_000,
  });
  const effective = useQuery({
    queryKey: ["bas-schedule-effective"],
    queryFn: () => apiFetch<Effective>("api/schedule/effective"),
    staleTime: 15_000,
  });

  const working = doc ?? loaded.data;
  const current = working?.schedules.find((s) => s.id === selectedId) ?? working?.schedules[0];

  const updateCurrent = (patch: Partial<ScheduleItem>) => {
    setDoc({
      ...working!,
      schedules: working!.schedules.map((s) => (s.id === current!.id ? { ...s, ...patch } : s)),
    });
  };

  const setDay = (d: DayKey, patch: Partial<DayBlock>) => {
    setDoc({
      ...working!,
      schedules: working!.schedules.map((s) =>
        s.id === current!.id
          ? { ...s, weekly: { ...s.weekly, [d]: { ...s.weekly[d], ...patch } } }
          : s,
      ),
    });
  };

  const addHoliday = () => {
    const today = new Date().toISOString().slice(0, 10);
    updateCurrent({ holidays: [...current!.holidays, { date: today, occupied: false }] });
  };

  const updateHoliday = (i: number, h: Partial<Holiday>) => {
    const next = [...current!.holidays];
    next[i] = { ...next[i], ...h };
    updateCurrent({ holidays: next });
  };

  const removeHoliday = (i: number) => {
    updateCurrent({ holidays: current!.holidays.filter((_, j) => j !== i) });
  };

  const addSchedule = () => {
    const blank = defaultSchedule(`sched_${Math.random().toString(36).slice(2, 8)}`, `Schedule ${working!.schedules.length + 1}`);
    setDoc({ ...working!, schedules: [...working!.schedules, blank] });
    setSelectedId(blank.id);
  };

  const removeSchedule = (id: string) => {
    const next = working!.schedules.filter((s) => s.id !== id);
    setDoc({ ...working!, schedules: next });
    if (selectedId === id) setSelectedId(next[0]?.id ?? "");
  };

  if (!working) {
    return <p className="text-sm text-muted-foreground">Loading schedule…</p>;
  }
  if (!current) {
    return <p className="text-sm text-muted-foreground">No schedules yet.</p>;
  }
  const pointByDevice = new Map<string, number>();
  for (const p of points.data?.items ?? []) {
    pointByDevice.set(p.deviceId, (pointByDevice.get(p.deviceId) ?? 0) + 1);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Occupancy schedule</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Generic weekly occupied/unoccupied windows with holiday day-picker overrides. Create multiple
          schedules and assign each one to multiple equipment devices.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-6 pt-6">
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm">
              Schedule
              <select
                className="ml-2 rounded border border-border bg-background px-2 py-1 text-sm"
                value={current.id}
                onChange={(e) => setSelectedId(e.target.value)}
              >
                {working.schedules.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="text-xs text-primary hover:underline" onClick={addSchedule}>
              Add schedule
            </button>
            {working.schedules.length > 1 ? (
              <button type="button" className="text-xs text-destructive" onClick={() => removeSchedule(current.id)}>
                Remove schedule
              </button>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm">
              Label{" "}
              <input
                className="ml-2 w-56 rounded border border-border bg-background px-2 py-1 text-sm"
                value={current.label ?? ""}
                onChange={(e) => updateCurrent({ label: e.target.value })}
              />
            </label>
            <label className="text-sm">
              Description{" "}
              <input
                className="ml-2 w-80 rounded border border-border bg-background px-2 py-1 text-sm"
                value={current.description ?? ""}
                onChange={(e) => updateCurrent({ description: e.target.value })}
              />
            </label>
            <button
              type="button"
              className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              onClick={() =>
                save.mutate(working, {
                  onSuccess: (res) => {
                    const s = res?.bacnetScheduleSync;
                    if (!s) {
                      setSyncNote("Saved schedule set.");
                    } else if (s.ok) {
                      setSyncNote(`Saved + pushed to BACnet schedule object "${s.scheduleName ?? "occupancy-schedule"}".`);
                    } else {
                      setSyncNote(`Saved locally, but BACnet schedule push failed: ${s.message ?? "unknown error"}`);
                    }
                  },
                })
              }
              disabled={save.isPending}
            >
              Save schedule set
            </button>
          </div>
          {syncNote ? <p className="text-xs text-muted-foreground">{syncNote}</p> : null}

          <div className="space-y-5">
            {DAYS.map((d) => {
              const row = current.weekly[d];
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
            <h2 className="text-sm font-semibold">Holiday overrides</h2>
            <button type="button" className="text-xs text-primary hover:underline" onClick={addHoliday}>
              Add holiday
            </button>
          </div>
          <ul className="space-y-2">
            {current.holidays.map((h, i) => (
              <li key={i} className="flex flex-wrap items-end gap-2 rounded-md border border-border/60 p-2">
                <label className="text-xs">
                  Mode
                  <select
                    className="ml-1 rounded border border-border bg-background px-1 py-0.5"
                    value={holidayMode(h)}
                    onChange={(e) => {
                      if (e.target.value === "single") {
                        updateHoliday(i, { date: h.date ?? h.start ?? "", start: undefined, end: undefined });
                      } else {
                        const d = h.date ?? new Date().toISOString().slice(0, 10);
                        updateHoliday(i, { date: undefined, start: h.start ?? d, end: h.end ?? d });
                      }
                    }}
                  >
                    <option value="single">Single day</option>
                    <option value="range">Date range</option>
                  </select>
                </label>
                <label className="text-xs">
                  {holidayMode(h) === "single" ? "Date" : "From"}
                  <input
                    type="date"
                    className="ml-1 rounded border border-border bg-background px-1 py-0.5"
                    value={h.date ?? h.start ?? ""}
                    onChange={(e) =>
                      holidayMode(h) === "single"
                        ? updateHoliday(i, { date: e.target.value })
                        : updateHoliday(i, { start: e.target.value })
                    }
                  />
                </label>
                {holidayMode(h) === "range" ? (
                  <label className="text-xs">
                    To
                    <input
                      type="date"
                      className="ml-1 rounded border border-border bg-background px-1 py-0.5"
                      value={h.end ?? h.start ?? ""}
                      onChange={(e) => updateHoliday(i, { end: e.target.value })}
                    />
                  </label>
                ) : null}
                <label className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={h.occupied}
                    onChange={(e) => updateHoliday(i, { occupied: e.target.checked })}
                  />
                  Occupied override (default OFF)
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
            <h2 className="text-sm font-semibold">Assign to equipment</h2>
          </div>
          <ul className="space-y-2">
            {(devices.data?.items ?? []).map((d) => {
              const assigned = current.assignments.includes(d.id);
              const eff = effective.data?.devices.find((x) => x.deviceId === d.id);
              return (
                <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/60 p-2 text-sm">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={assigned}
                      onChange={(e) =>
                        updateCurrent({
                          assignments: e.target.checked
                            ? [...current.assignments, d.id]
                            : current.assignments.filter((x) => x !== d.id),
                        })
                      }
                    />
                    <span className="font-medium">{d.displayName}</span>
                    <span className="font-mono text-xs text-muted-foreground">{d.id}</span>
                    <span className="text-xs text-muted-foreground">{pointByDevice.get(d.id) ?? 0} points</span>
                  </label>
                  <span className={`text-xs ${eff?.occupied ? "text-emerald-600" : "text-muted-foreground"}`}>
                    {eff?.occupied ? "Occupied" : "Unoccupied"} ({eff?.reason ?? "n/a"})
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="text-xs text-muted-foreground">
            Effective evaluation time (host OS): {effective.data?.localTime ?? "loading"}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
