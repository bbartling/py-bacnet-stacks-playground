import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiFetch } from "../lib/api-client";
import { useAuth } from "./auth-context";
import { logger } from "../lib/logger";

export type Building = {
  site_id: string;
  building_id: string;
  building_scope?: string;
};

type SiteContextValue = {
  buildings: Building[];
  siteId: string;
  buildingId: string;
  setSiteId: (id: string) => void;
  setBuildingId: (id: string) => void;
  refreshBuildings: () => Promise<void>;
};

const SiteContext = createContext<SiteContextValue | null>(null);

export function SiteProvider({ children }: { children: ReactNode }) {
  const { ready: authReady, authenticated } = useAuth();
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [siteId, setSiteId] = useState("");
  const [buildingId, setBuildingId] = useState("");

  const refreshBuildings = useCallback(async () => {
    const data = await apiFetch<{ buildings: Building[] }>("/api/buildings");
    const list = data.buildings || [];
    setBuildings(list);
    if (!list.length) return;
    setSiteId((cur) => {
      if (cur && list.some((b) => b.site_id === cur)) return cur;
      return list[0].site_id;
    });
    setBuildingId((curB) => {
      const site = siteId || list[0].site_id;
      const forSite = list.filter((b) => b.site_id === site);
      if (curB && forSite.some((b) => b.building_id === curB)) return curB;
      return forSite[0]?.building_id || list[0].building_id;
    });
    logger.debug("site", `buildings loaded (${list.length})`);
  }, [siteId]);

  useEffect(() => {
    if (!authReady || !authenticated) return;
    void refreshBuildings().catch((e) => logger.error("site", "buildings failed", e));
  }, [authReady, authenticated, refreshBuildings]);

  useEffect(() => {
    const forSite = buildings.filter((b) => b.site_id === siteId);
    if (forSite.length && !forSite.some((b) => b.building_id === buildingId)) {
      setBuildingId(forSite[0].building_id);
    }
  }, [siteId, buildings, buildingId]);

  const value = useMemo(
    () => ({
      buildings,
      siteId,
      buildingId,
      setSiteId,
      setBuildingId,
      refreshBuildings,
    }),
    [buildings, siteId, buildingId, refreshBuildings],
  );

  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>;
}

export function useSite() {
  const ctx = useContext(SiteContext);
  if (!ctx) throw new Error("useSite must be used within SiteProvider");
  return ctx;
}
