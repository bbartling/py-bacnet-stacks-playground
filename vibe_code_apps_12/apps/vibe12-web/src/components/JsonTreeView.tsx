/** Collapsible tree for API health / config JSON (objects, arrays, primitives). */

type JsonValue = unknown;

function isRecord(v: JsonValue): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function formatPrimitive(v: JsonValue): string {
  if (v === null) return "null";
  if (typeof v === "string") return v;
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(v);
  return String(v);
}

function primitiveClass(v: JsonValue): string {
  if (v === null) return "json-null";
  if (typeof v === "string") return "json-string";
  if (typeof v === "boolean") return "json-bool";
  if (typeof v === "number") return "json-number";
  return "";
}

function arrayPreview(items: JsonValue[]): string {
  if (!items.length) return "[]";
  const prim = items.every((x) => x === null || ["string", "number", "boolean"].includes(typeof x));
  if (prim && items.length <= 4) {
    return `[${items.map((x) => formatPrimitive(x)).join(", ")}]`;
  }
  return `[${items.length} items]`;
}

function Node({
  label,
  value,
  depth,
  openDepth,
}: {
  label: string;
  value: JsonValue;
  depth: number;
  openDepth: number;
}) {
  const defaultOpen = depth < openDepth;
  if (Array.isArray(value)) {
    const allPrimitive = value.every(
      (x) => x === null || ["string", "number", "boolean"].includes(typeof x),
    );
    if (allPrimitive && value.length <= 12) {
      return (
        <div className="json-tree-row" style={{ paddingLeft: depth * 14 }}>
          <span className="json-tree-key">{label}</span>
          <span className="json-tree-sep">:</span>
          <span className="json-chip-list">
            {value.map((item, i) => (
              <span key={i} className={`json-chip ${primitiveClass(item)}`}>
                {formatPrimitive(item)}
              </span>
            ))}
          </span>
        </div>
      );
    }
    return (
      <details className="json-tree-branch" open={defaultOpen}>
        <summary className="json-tree-summary" style={{ paddingLeft: depth * 14 }}>
          <span className="json-tree-key">{label}</span>
          <span className="json-tree-meta muted">{arrayPreview(value)}</span>
        </summary>
        <div className="json-tree-children">
          {value.map((item, i) => (
            <Node key={i} label={String(i)} value={item} depth={depth + 1} openDepth={openDepth} />
          ))}
        </div>
      </details>
    );
  }

  if (isRecord(value)) {
    const keys = Object.keys(value);
    if (!keys.length) {
      return (
        <div className="json-tree-row" style={{ paddingLeft: depth * 14 }}>
          <span className="json-tree-key">{label}</span>
          <span className="json-tree-sep">:</span>
          <span className="json-null">{"{}"}</span>
        </div>
      );
    }
    return (
      <details className="json-tree-branch" open={defaultOpen}>
        <summary className="json-tree-summary" style={{ paddingLeft: depth * 14 }}>
          <span className="json-tree-key">{label}</span>
          <span className="json-tree-meta muted">{`{${keys.length} keys}`}</span>
        </summary>
        <div className="json-tree-children">
          {keys.map((k) => (
            <Node key={k} label={k} value={value[k]} depth={depth + 1} openDepth={openDepth} />
          ))}
        </div>
      </details>
    );
  }

  const text = formatPrimitive(value);
  const long = typeof value === "string" && text.length > 72;

  return (
    <div className="json-tree-row" style={{ paddingLeft: depth * 14 }}>
      <span className="json-tree-key">{label}</span>
      <span className="json-tree-sep">:</span>
      <span className={`json-tree-value ${primitiveClass(value)} ${long ? "json-wrap" : ""}`}>
        {typeof value === "string" ? `"${text}"` : text}
      </span>
    </div>
  );
}

export function JsonTreeView({
  data,
  rootLabel = "response",
  openDepth = 1,
}: {
  data: JsonValue;
  rootLabel?: string;
  /** How many nesting levels start expanded (0 = collapsed root only). */
  openDepth?: number;
}) {
  if (data === null || data === undefined) {
    return <p className="muted">No data</p>;
  }

  if (!isRecord(data) && !Array.isArray(data)) {
    return (
      <div className="json-tree">
        <span className={`json-tree-value ${primitiveClass(data)}`}>{formatPrimitive(data)}</span>
      </div>
    );
  }

  if (Array.isArray(data)) {
    return (
      <div className="json-tree">
        <Node label={rootLabel} value={data} depth={0} openDepth={openDepth} />
      </div>
    );
  }

  const keys = Object.keys(data);
  return (
    <div className="json-tree">
      {keys.map((k) => (
        <Node key={k} label={k} value={data[k]} depth={0} openDepth={openDepth} />
      ))}
    </div>
  );
}
