import { FormEvent, useState } from "react";
import { apiFetch } from "../lib/api-client";
import { logger } from "../lib/logger";
import { TopBar } from "../components/layout/TopBar";
import { useSite } from "../contexts/site-context";

function slugify(s: string) {
  return s
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function SitesPage() {
  const { buildings, refreshBuildings, setSiteId, setBuildingId } = useSite();
  const [siteId, setSiteInput] = useState("");
  const [buildingId, setBuildingInput] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [status, setStatus] = useState("");

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    const sid = slugify(siteId);
    const bid = slugify(buildingId);
    if (!sid || !bid) {
      setStatus("Enter site and building IDs.");
      return;
    }
    try {
      await apiFetch("/api/buildings", {
        method: "POST",
        body: JSON.stringify({
          site_id: sid,
          building_id: bid,
          display_name: displayName || `${sid} / ${bid}`,
        }),
      });
      setStatus(`Created ${sid} / ${bid}`);
      await refreshBuildings();
      setSiteId(sid);
      setBuildingId(bid);
      logger.info("sites", `created ${sid}/${bid}`);
    } catch (err) {
      setStatus("Create failed — see console");
      logger.error("sites", "create failed", err);
    }
  }

  return (
    <div className="stack-page">
      <TopBar
        title="Sites & BRICK"
        subtitle="Register site/building before edge MQTT · then use Data Model for BRICK import"
      />
      <div className="card">
        <h3 className="title">Create site / building</h3>
        <p className="muted">
          Registers DynamoDB meta and an empty canonical model. Edge must publish MQTT to{" "}
          <code>vibe12/&#123;site&#125;/&#123;building&#125;/…/telemetry</code>.
        </p>
        <form className="site-form" onSubmit={(e) => void onCreate(e)}>
          <label>
            Site ID
            <input value={siteId} onChange={(e) => setSiteInput(e.target.value)} placeholder="demo" />
          </label>
          <label>
            Building ID
            <input
              value={buildingId}
              onChange={(e) => setBuildingInput(e.target.value)}
              placeholder="office-tower"
            />
          </label>
          <label>
            Display name
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Optional label"
            />
          </label>
          <button type="submit">Create</button>
          <span className="muted">{status}</span>
        </form>
      </div>
      <div className="card">
        <h3 className="title">Registered buildings</h3>
        <div className="registry-wrap">
          <table className="registry-table">
            <thead>
              <tr>
                <th>Site</th>
                <th>Building</th>
                <th>Scope</th>
              </tr>
            </thead>
            <tbody>
              {buildings.length === 0 ? (
                <tr>
                  <td colSpan={3} className="muted">
                    No buildings yet — create one or wait for edge ingest.
                  </td>
                </tr>
              ) : (
                buildings.map((b) => (
                  <tr key={`${b.site_id}-${b.building_id}`}>
                    <td>{b.site_id}</td>
                    <td>{b.building_id}</td>
                    <td className="mono">{b.building_scope || `${b.site_id}#${b.building_id}`}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
