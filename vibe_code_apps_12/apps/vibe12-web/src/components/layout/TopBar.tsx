import { useSite } from "../../contexts/site-context";

type Props = { title: string; subtitle?: string };

export function TopBar({ title, subtitle }: Props) {
  const { buildings, siteId, buildingId, setSiteId, setBuildingId, refreshBuildings } = useSite();
  const sites = [...new Set(buildings.map((b) => b.site_id))];
  const buildingsForSite = buildings.filter((b) => b.site_id === siteId);

  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">{title}</h1>
        {subtitle ? <p className="topbar-subtitle">{subtitle}</p> : null}
      </div>
      <div className="topbar-actions">
        <label className="inline-label" htmlFor="site-select">
          Site
        </label>
        <select
          id="site-select"
          className="site-selector"
          value={siteId}
          onChange={(e) => setSiteId(e.target.value)}
        >
          {sites.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <label className="inline-label" htmlFor="bld-select">
          Building
        </label>
        <select
          id="bld-select"
          className="site-selector"
          value={buildingId}
          onChange={(e) => setBuildingId(e.target.value)}
        >
          {buildingsForSite.map((b) => (
            <option key={b.building_id} value={b.building_id}>
              {b.building_id}
            </option>
          ))}
        </select>
        <button type="button" className="secondary-btn" onClick={() => void refreshBuildings()}>
          Refresh
        </button>
      </div>
    </header>
  );
}
