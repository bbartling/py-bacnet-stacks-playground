import { useState } from 'react';
import type { BacnetPoint } from '../shared/scheduleTypes';

type Props = {
  points: BacnetPoint[];
  onChange: (points: BacnetPoint[]) => void;
  /** When set, copy explains these points belong to the active schedule profile */
  profileName?: string;
};

export function BacnetPointsEditor({
  points,
  onChange,
  profileName,
}: Props) {
  const [name, setName] = useState('');
  const [objectId, setObjectId] = useState('');

  function addPoint() {
    const trimmed = name.trim();
    if (!trimmed) return;
    const id = crypto.randomUUID();
    onChange([
      ...points,
      {
        id,
        name: trimmed,
        objectId: objectId.trim() || undefined,
      },
    ]);
    setName('');
    setObjectId('');
  }

  function updatePoint(id: string, patch: Partial<Pick<BacnetPoint, 'name' | 'objectId'>>) {
    onChange(
      points.map((p) => {
        if (p.id !== id) return p;
        const next: BacnetPoint = { ...p, ...patch };
        if ('objectId' in patch) {
          next.objectId = patch.objectId?.trim() || undefined;
        }
        return next;
      })
    );
  }

  function removePoint(id: string) {
    onChange(points.filter((p) => p.id !== id));
  }

  return (
    <section className="panel" aria-labelledby="bacnet-heading">
      <h2 id="bacnet-heading">BACnet points</h2>
      <p className="section-hint">
        {profileName ? (
          <>
            Points assigned to the <strong>{profileName}</strong> schedule only
            (switch schedule above to edit another profile&apos;s list). Object ID
            is optional metadata for integration (e.g. AV:1).
          </>
        ) : (
          <>
            Configure supervisory points. Object ID is optional metadata for
            integration (e.g. AV:1).
          </>
        )}
      </p>
      <div className="bacnet-table">
        <div className="bacnet-row bacnet-row-head">
          <span>Display name</span>
          <span>BACnet object ID (optional)</span>
          <span className="bacnet-actions-col" />
        </div>
        {points.map((p) => (
          <div key={p.id} className="bacnet-row">
            <input
              className="control"
              aria-label={`Name for point ${p.id}`}
              value={p.name}
              onChange={(e) => updatePoint(p.id, { name: e.target.value })}
            />
            <input
              className="control"
              aria-label={`Object ID for ${p.name}`}
              placeholder="e.g. AV:1"
              value={p.objectId ?? ''}
              onChange={(e) => updatePoint(p.id, { objectId: e.target.value })}
            />
            <div className="bacnet-actions">
              <button
                type="button"
                className="btn danger"
                onClick={() => removePoint(p.id)}
              >
                Remove
              </button>
            </div>
          </div>
        ))}
        <div className="bacnet-row bacnet-add">
          <input
            className="control"
            placeholder="New point name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addPoint()}
          />
          <input
            className="control"
            placeholder="Object ID (optional)"
            value={objectId}
            onChange={(e) => setObjectId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addPoint()}
          />
          <div className="bacnet-actions">
            <button type="button" className="btn primary" onClick={addPoint}>
              Add point
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
