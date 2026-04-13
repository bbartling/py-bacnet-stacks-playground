import { useQuery } from "@tanstack/react-query";
import { vtFetch } from "@/lib/volttron-fetch";

type Health = {
  status: string;
  appTitle: string;
  siteName: string;
  lastPublishAt: string | null;
  counts: { devices: number; points: number; activeAlarms: number };
};

export function BasHealthStrip() {
  const { data } = useQuery({
    queryKey: ["bas-health"],
    queryFn: () => vtFetch<Health>("api/health"),
    refetchInterval: 15_000,
  });

  if (!data) {
    return (
      <div className="border-b border-border/60 bg-muted/30 px-6 py-1.5 text-xs text-muted-foreground">
        Loading platform health…
      </div>
    );
  }

  const ok = data.status === "ok";
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border/60 bg-muted/30 px-6 py-1.5 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <span
          className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-destructive"}`}
          aria-hidden
        />
        <span className="font-medium text-foreground">{data.appTitle}</span>
        <span>· {data.siteName}</span>
      </span>
      <span>
        Last BACnet publish:{" "}
        <span className="font-mono text-foreground">{data.lastPublishAt ?? "—"}</span>
      </span>
      <span>
        Devices {data.counts.devices} · Points {data.counts.points} · Active alarms{" "}
        {data.counts.activeAlarms}
      </span>
    </div>
  );
}
