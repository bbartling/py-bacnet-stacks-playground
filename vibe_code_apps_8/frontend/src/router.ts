import { mountShell, type ShellHandles } from "./shell";
import { pathForRoute, routeFromPathname, type RouteId } from "./routes";
import { mountAlarms } from "./views/alarms";
import { mountDocs } from "./views/docs";
import { mountDriver } from "./views/driver";
import { mountFaults } from "./views/faults";
import { mountLivePoints } from "./views/live-points";
import { mountOverview } from "./views/overview";
import { mountSchedule } from "./views/schedule";
import { mountSystem } from "./views/system";
import type { MountFn, ViewCtx } from "./views/types";

const mounts: Record<RouteId, MountFn> = {
  overview: mountOverview,
  "live-points": mountLivePoints,
  driver: mountDriver,
  system: mountSystem,
  faults: mountFaults,
  alarms: mountAlarms,
  schedule: mountSchedule,
  docs: mountDocs,
};

export function startRouter(root: HTMLElement): () => void {
  let route = routeFromPathname();
  let unmount: (() => void) | null = null;
  let shell: ShellHandles | null = null;

  const ctx: ViewCtx = {
    navigate: (r: RouteId) => {
      const url = pathForRoute(r);
      history.pushState(null, "", url);
      applyRoute(r);
    },
  };

  const applyRoute = (r: RouteId) => {
    route = r;
    shell?.setRoute(r);
    unmount?.();
    unmount = null;
    if (!shell) return;
    unmount = mounts[r](shell.outlet, ctx);
  };

  shell = mountShell(root, {
    navigate: ctx.navigate,
    getRoute: () => route,
  });

  const onPop = () => {
    applyRoute(routeFromPathname());
  };
  window.addEventListener("popstate", onPop);

  applyRoute(route);

  return () => {
    window.removeEventListener("popstate", onPop);
    unmount?.();
    shell?.dispose();
    shell = null;
    unmount = null;
  };
}
