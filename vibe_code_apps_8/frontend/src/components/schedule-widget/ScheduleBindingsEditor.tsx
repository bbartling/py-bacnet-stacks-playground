import type { BacnetBinding } from "./scheduleTypes";

type PointOpt = { id: string; deviceId: string; label: string; name: string };

type Props = {
  bindings: BacnetBinding[];
  onChange: (next: BacnetBinding[]) => void;
  profileName: string;
  points: PointOpt[];
};

export function ScheduleBindingsEditor({ bindings, onChange, profileName, points }: Props) {
  function addBinding() {
    const first = points[0];
    if (!first) return;
    onChange([
      ...bindings,
      {
        id: crypto.randomUUID(),
        pointId: first.id,
        name: first.label || first.name,
        objectId: undefined,
      },
    ]);
  }

  function updateBinding(id: string, patch: Partial<BacnetBinding>) {
    onChange(
      bindings.map((b) => {
        if (b.id !== id) return b;
        const next = { ...b, ...patch };
        if (patch.pointId) {
          const p = points.find((x) => x.id === patch.pointId);
          if (p) next.name = p.label || p.name;
        }
        return next;
      }),
    );
  }

  function removeBinding(id: string) {
    onChange(bindings.filter((b) => b.id !== id));
  }

  return (
    <section className="panel" aria-labelledby="bacnet-heading">
      <h2 id="bacnet-heading">BACnet / supervisor bindings</h2>
      <p className="section-hint">
        Rows reference <strong>configured points</strong> from the BAS Lite driver (same ids as Live Points). Use this
        list as AI context for occupancy-related outputs; BACnet schedule push still uses the hosted weekly pattern on
        diy-bacnet.
      </p>
      <p className="section-hint">
        Active schedule: <strong>{profileName}</strong>
      </p>
      <div className="bacnet-table">
        <div className="bacnet-row bacnet-row-head">
          <span>Supervisor point</span>
          <span>Display label</span>
          <span>BACnet object hint (optional)</span>
          <span className="bacnet-actions-col">&nbsp;</span>
        </div>
        {bindings.map((b) => (
          <div key={b.id} className="bacnet-row">
            <select
              className="control"
              aria-label="Supervisor point"
              value={b.pointId}
              onChange={(e) => updateBinding(b.id, { pointId: e.target.value })}
            >
              {points.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.deviceId} — {p.label || p.name}
                </option>
              ))}
            </select>
            <input
              className="control"
              aria-label="Label"
              value={b.name}
              onChange={(e) => updateBinding(b.id, { name: e.target.value })}
            />
            <input
              className="control"
              aria-label="Object hint"
              placeholder="e.g. multi-state-value,1"
              value={b.objectId ?? ""}
              onChange={(e) => updateBinding(b.id, { objectId: e.target.value || undefined })}
            />
            <div className="bacnet-actions">
              <button type="button" className="btn danger" onClick={() => removeBinding(b.id)}>
                Remove
              </button>
            </div>
          </div>
        ))}
        <div className="bacnet-row bacnet-add">
          <button type="button" className="btn primary" onClick={addBinding} disabled={!points.length}>
            Add binding
          </button>
        </div>
      </div>
    </section>
  );
}
