import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { ScheduleIslandApp } from "./ScheduleIslandApp";
import type { ApiScheduleDoc } from "./scheduleApiBridge";
import "./schedule-island.css";
import "react-day-picker/style.css";

let root: Root | null = null;

export type ScheduleIslandMountProps = {
  initialDoc: ApiScheduleDoc;
  onSave: (doc: ApiScheduleDoc) => Promise<void>;
  onAfterSave?: () => void;
};

export function mountScheduleIsland(el: HTMLElement, props: ScheduleIslandMountProps): void {
  unmountScheduleIsland();
  const r = createRoot(el);
  root = r;
  r.render(
    <StrictMode>
      <ScheduleIslandApp {...props} />
    </StrictMode>,
  );
}

export function unmountScheduleIsland(): void {
  root?.unmount();
  root = null;
}
