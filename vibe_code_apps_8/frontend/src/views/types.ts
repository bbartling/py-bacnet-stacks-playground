import type { RouteId } from "../routes";

export type ViewCtx = {
  navigate: (r: RouteId) => void;
};

export type MountFn = (outlet: HTMLElement, ctx: ViewCtx) => () => void;
