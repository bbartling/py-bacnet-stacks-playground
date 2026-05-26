import { Link } from "react-router-dom";
import { StatusDot } from "./StatusDot";

export type BuildingStatusRow = {
  site_id: string;
  building_id: string;
  ingest_status: string;
  series_total: number;
  series_flowing: number;
  cloud_ingest_ok: boolean;
  last_activity_ms: number;
  iot_mqtt?: {
    label?: string;
    thing_name?: string;
    client_id?: string;
    mqtt_connected?: boolean | null;
    mqtt_status?: string;
    disconnect_reason?: string;
    iot_error?: string;
  };
};

export type EdgeStatusPayload = {
  buildings: BuildingStatusRow[];
  series?: unknown[];
  freshness_thresholds_minutes?: Record<string, number>;
  iot_connectivity?: {
    configured?: boolean;
    hint?: string;
    things?: unknown[];
  };
  status_sources?: Record<string, string>;
};

function fmtTs(ms: number) {
  if (!ms) return "—";
  return new Date(ms).toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

function iotDotStatus(row: BuildingStatusRow): string {
  const iot = row.iot_mqtt;
  if (!iot) return "offline";
  if (iot.mqtt_connected === true) return "green";
  if (iot.mqtt_connected === false) return "red";
  if (iot.mqtt_status === "api_error") return "orange";
  return "offline";
}

type Props = {
  data: EdgeStatusPayload | null;
  compact?: boolean;
  showSeriesLink?: boolean;
};

export function EdgeStatusPanel({ data, compact, showSeriesLink }: Props) {
  if (!data) {
    return <p className="muted">Loading edge status…</p>;
  }

  const thresholds = data.freshness_thresholds_minutes || {};
  const buildings = data.buildings || [];

  return (
    <div className={`edge-status-panel ${compact ? "edge-status-compact" : ""}`}>
      <div className="edge-status-legend muted">
        <span>
          <strong>Telemetry</strong> (DynamoDB): green &lt;{thresholds.green ?? 20}m · yellow &lt;
          {thresholds.yellow ?? 40}m · orange &lt;{thresholds.orange ?? 60}m
        </span>
        {data.iot_connectivity?.configured ? (
          <span className="edge-legend-iot">
            <strong>IoT Core</strong> (thing API): connected / disconnected
          </span>
        ) : (
          <span className="edge-legend-iot">
            IoT thing poll not configured — ingest dots still show telemetry path
          </span>
        )}
      </div>

      <table className="registry-table edge-status-table">
        <thead>
          <tr>
            <th />
            <th>Site / building</th>
            <th>Telemetry</th>
            <th>Flowing</th>
            <th>Last ingest</th>
            {data.iot_connectivity?.configured ? <th>IoT MQTT</th> : null}
          </tr>
        </thead>
        <tbody>
          {buildings.length === 0 ? (
            <tr>
              <td colSpan={6} className="muted">
                No buildings in registry — publish edge MQTT or create a site.
              </td>
            </tr>
          ) : (
            buildings.map((b) => (
              <tr key={`${b.site_id}#${b.building_id}`}>
                <td>
                  <StatusDot status={b.ingest_status} title="Telemetry freshness" />
                </td>
                <td>
                  {b.site_id}/{b.building_id}
                </td>
                <td>{b.cloud_ingest_ok ? "OK" : "stale"}</td>
                <td>
                  {b.series_flowing}/{b.series_total}
                </td>
                <td className="mono small">{fmtTs(b.last_activity_ms)}</td>
                {data.iot_connectivity?.configured ? (
                  <td className="iot-mqtt-cell">
                    {b.iot_mqtt ? (
                      <>
                        <StatusDot status={iotDotStatus(b)} title={b.iot_mqtt.mqtt_status || ""} />
                        <span className="iot-mqtt-label">
                          {b.iot_mqtt.label || b.iot_mqtt.client_id || b.iot_mqtt.thing_name}
                        </span>
                        {b.iot_mqtt.mqtt_connected === true ? (
                          <span className="muted"> connected</span>
                        ) : null}
                        {b.iot_mqtt.mqtt_connected === false ? (
                          <span className="warn-text"> offline</span>
                        ) : null}
                        {b.iot_mqtt.iot_error ? (
                          <span className="muted" title={b.iot_mqtt.iot_error}>
                            {" "}
                            (API)
                          </span>
                        ) : null}
                      </>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                ) : null}
              </tr>
            ))
          )}
        </tbody>
      </table>

      {!compact && data.iot_connectivity?.hint ? (
        <p className="muted edge-iot-hint">{data.iot_connectivity.hint}</p>
      ) : null}

      {showSeriesLink ? (
        <p className="edge-detail-link">
          <Link to="/edge-devices">All series detail →</Link>
        </p>
      ) : null}
    </div>
  );
}
