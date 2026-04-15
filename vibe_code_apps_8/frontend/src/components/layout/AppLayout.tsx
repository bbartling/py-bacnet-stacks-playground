import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { BasHealthStrip } from "@/components/dashboard/BasHealthStrip";
import { useBasWebSocket } from "@/hooks/use-bas-websocket";

export function AppLayout() {
  useBasWebSocket();
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <BasHealthStrip />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl px-6 py-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
