import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { ScheduleWidgetBody } from "@/components/schedule-widget/ScheduleWidgetBody";
import type { HolidayEntry, ScheduleProfile, WeekFormState } from "@/components/schedule-widget/scheduleTypes";
import { apiFetch } from "@/lib/bas-fetch";
import {
  defaultWeekForm,
  entriesToHolidays,
  holidaysToEntries,
  mergeProfileIntoItem,
  profileToWeekly,
  scheduleItemToProfile,
  type ScheduleDocBridge,
  type ScheduleItemBridge,
  parseScheduleAiJson,
} from "@/lib/schedule-bridge";

import "@/components/schedule-widget/schedule-widget.css";

type Effective = {
  localTime: string;
  devices: { deviceId: string; deviceName: string; occupied: boolean; reason: string }[];
};

function newBlankSchedule(id: string, label: string): ScheduleItemBridge {
  return {
    id,
    label,
    description: "",
    assignments: [],
    weekly: profileToWeekly(defaultWeekForm()),
    holidays: [],
    bacnetBindings: [],
  };
}

export function BasSchedulePage() {
  const qc = useQueryClient();
  const [doc, setDoc] = useState<ScheduleDocBridge | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [newProfileName, setNewProfileName] = useState("");
  const [holidayDraft, setHolidayDraft] = useState<HolidayEntry[]>([]);
  const [syncNote, setSyncNote] = useState("");
  const [aiJson, setAiJson] = useState("");
  const [aiError, setAiError] = useState<string | null>(null);

  const loaded = useQuery({
    queryKey: ["bas-schedule"],
    queryFn: () => apiFetch<ScheduleDocBridge>("api/schedule"),
  });

  useEffect(() => {
    if (!loaded.data) return;
    setDoc((prev) => prev ?? structuredClone(loaded.data));
    setSelectedId((prev) => prev || loaded.data.schedules?.[0]?.id || "");
  }, [loaded.data]);

  const currentItem = useMemo(
    () => doc?.schedules.find((s) => s.id === selectedId) ?? doc?.schedules[0],
    [doc, selectedId],
  );

  const prevSelectedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!doc || !selectedId) return;
    if (prevSelectedRef.current === selectedId) return;
    prevSelectedRef.current = selectedId;
    const item = doc.schedules.find((s) => s.id === selectedId);
    if (item) setHolidayDraft(holidaysToEntries(item.holidays));
  }, [doc, selectedId]);

  const save = useMutation({
    mutationFn: async (body: ScheduleDocBridge) =>
      apiFetch<{ status: string; bacnetScheduleSync?: { ok?: boolean; message?: string; scheduleName?: string } }>(
        "api/schedule",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bas-schedule"] });
      qc.invalidateQueries({ queryKey: ["bas-schedule-effective"] });
    },
  });

  const points = useQuery({
    queryKey: ["bas-points"],
    queryFn: () => apiFetch<{ items: { id: string; deviceId: string; label: string; name: string }[] }>("api/points"),
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

  const profiles: ScheduleProfile[] = useMemo(
    () => (doc?.schedules ?? []).map((s) => scheduleItemToProfile(s)),
    [doc],
  );

  const patchCurrentItem = useCallback(
    (fn: (item: ScheduleItemBridge) => ScheduleItemBridge) => {
      if (!doc || !selectedId) return;
      setDoc({
        ...doc,
        schedules: doc.schedules.map((s) => (s.id === selectedId ? fn(s) : s)),
      });
    },
    [doc, selectedId],
  );

  const onUpdateActiveForm = useCallback(
    (updater: (prev: WeekFormState) => WeekFormState) => {
      patchCurrentItem((item) => {
        const prof = scheduleItemToProfile(item);
        const nextForm = updater(prof.form);
        return mergeProfileIntoItem(item, { ...prof, form: nextForm }, holidayDraft);
      });
    },
    [holidayDraft, patchCurrentItem],
  );

  const onBindingsChange = useCallback(
    (next: ScheduleProfile["bacnetBindings"]) => {
      patchCurrentItem((item) => ({ ...item, bacnetBindings: next }));
    },
    [patchCurrentItem],
  );

  const onHolidaysChange = useCallback(
    (h: HolidayEntry[]) => {
      setHolidayDraft(h);
      patchCurrentItem((item) => ({ ...item, holidays: entriesToHolidays(h) }));
    },
    [patchCurrentItem],
  );

  const addSchedule = () => {
    if (!doc) return;
    const name = newProfileName.trim() || `Schedule ${doc.schedules.length + 1}`;
    const id = `sched_${crypto.randomUUID().replace(/-/g, "").slice(0, 10)}`;
    const blank = newBlankSchedule(id, name);
    setDoc({ ...doc, schedules: [...doc.schedules, blank] });
    setSelectedId(id);
    setNewProfileName("");
  };

  const deleteActive = () => {
    if (!doc || doc.schedules.length <= 1) return;
    const next = doc.schedules.filter((s) => s.id !== selectedId);
    setDoc({ ...doc, schedules: next });
    setSelectedId(next[0]?.id ?? "");
  };

  const applyAiImport = () => {
    setAiError(null);
    try {
      const imported = parseScheduleAiJson(aiJson);
      setDoc(structuredClone(imported));
      setSelectedId(imported.schedules[0]?.id ?? "");
      setHolidayDraft(holidaysToEntries(imported.schedules[0]?.holidays ?? []));
      setAiJson("");
      setSyncNote("Imported schedule JSON into the editor (not saved until you click Save).");
    } catch (e) {
      setAiError((e as Error).message);
    }
  };

  const exportDocJson = () => {
    if (!doc) return;
    const blob = new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "bas-lite-schedule-export.json";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (!doc) {
    return <p className="text-sm text-muted-foreground">Loading schedule…</p>;
  }
  if (!currentItem) {
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
          Weekly visual from the standalone schedule widget demo, wired to BAS Lite schedule JSON, BACnet hosted
          schedule push, and supervisor point ids from your driver setup.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              Schedule name
              <input
                className="ml-2 w-56 rounded border border-border bg-background px-2 py-1 text-sm"
                value={currentItem.label}
                onChange={(e) =>
                  patchCurrentItem((s) => ({
                    ...s,
                    label: e.target.value,
                  }))
                }
              />
            </label>
            <label className="text-sm">
              Hosted BACnet name
              <input
                className="ml-2 w-48 rounded border border-border bg-background px-2 py-1 font-mono text-xs"
                value={doc.hostedScheduleName ?? "occupancy-schedule"}
                onChange={(e) => setDoc({ ...doc, hostedScheduleName: e.target.value })}
                title="Passed to diy-bacnet server_update_schedule"
              />
            </label>
            <button
              type="button"
              className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              onClick={() =>
                save.mutate(doc, {
                  onSuccess: (res) => {
                    const s = res?.bacnetScheduleSync;
                    if (!s) setSyncNote("Saved schedule set.");
                    else if (s.ok)
                      setSyncNote(`Saved + pushed to BACnet schedule object "${s.scheduleName ?? "occupancy-schedule"}".`);
                    else setSyncNote(`Saved locally, but BACnet schedule push failed: ${s.message ?? "unknown error"}`);
                  },
                })
              }
              disabled={save.isPending}
            >
              Save schedule set
            </button>
            <button type="button" className="rounded border border-border px-3 py-2 text-sm hover:bg-muted" onClick={exportDocJson}>
              Export JSON
            </button>
          </div>
          {syncNote ? <p className="text-xs text-muted-foreground">{syncNote}</p> : null}

          <div className="space-y-2 rounded-md border border-border/60 bg-muted/30 p-3">
            <p className="text-xs font-medium text-muted-foreground">AI-assisted import (paste JSON)</p>
            <textarea
              className="min-h-[120px] w-full rounded border border-border bg-background p-2 font-mono text-xs"
              placeholder='{ "version": 2, "schedules": [ ... ] }'
              value={aiJson}
              onChange={(e) => setAiJson(e.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              <button type="button" className="rounded border border-border px-3 py-1 text-xs hover:bg-muted" onClick={applyAiImport}>
                Merge into editor
              </button>
              {aiError ? <span className="text-xs text-destructive">{aiError}</span> : null}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="bas-schedule-widget">
        <div className="layout">
          <ScheduleWidgetBody
            schedules={profiles}
            activeScheduleId={selectedId}
            onSelectSchedule={setSelectedId}
            newProfileName={newProfileName}
            onNewProfileName={setNewProfileName}
            onAddProfile={addSchedule}
            onDeleteActiveProfile={deleteActive}
            onUpdateActiveForm={onUpdateActiveForm}
            onBindingsChange={onBindingsChange}
            holidays={holidayDraft}
            onHolidaysChange={onHolidaysChange}
            points={points.data?.items ?? []}
          />
        </div>
      </div>

      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Assign to equipment</h2>
          </div>
          <ul className="space-y-2">
            {(devices.data?.items ?? []).map((d) => {
              const assigned = currentItem.assignments.includes(d.id);
              const eff = effective.data?.devices.find((x) => x.deviceId === d.id);
              return (
                <li
                  key={d.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/60 p-2 text-sm"
                >
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={assigned}
                      onChange={(e) =>
                        patchCurrentItem((s) => ({
                          ...s,
                          assignments: e.target.checked
                            ? [...s.assignments, d.id]
                            : s.assignments.filter((x) => x !== d.id),
                        }))
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
