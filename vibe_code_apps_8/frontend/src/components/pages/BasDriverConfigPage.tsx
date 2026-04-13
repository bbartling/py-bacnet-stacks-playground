import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { vtFetch } from "@/lib/volttron-fetch";
import { ChevronRight, FileJson, Table2 } from "lucide-react";

type ListResp = { items: string[]; stderr: string; exitCode: number };
type GetResp = { name: string; content: string; stderr: string; exitCode: number };

function groupConfigs(names: string[]) {
  const root: Record<string, string[]> = {};
  for (const n of names) {
    const seg = n.split("/")[0] || "_";
    root[seg] = root[seg] ?? [];
    root[seg].push(n);
  }
  for (const k of Object.keys(root)) {
    root[k].sort();
  }
  return root;
}

export function BasDriverConfigPage() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [isCsv, setIsCsv] = useState(false);

  const list = useQuery({
    queryKey: ["driver-configs"],
    queryFn: () => vtFetch<ListResp>("api/driver/configs"),
    refetchInterval: 30_000,
  });

  const detail = useQuery({
    queryKey: ["driver-config", selected],
    queryFn: () => vtFetch<GetResp>(`api/driver/config?name=${encodeURIComponent(selected!)}`),
    enabled: !!selected,
  });

  useEffect(() => {
    if (detail.data?.content != null) {
      setText(detail.data.content);
      setIsCsv(
        Boolean(selected?.endsWith(".csv") || selected?.startsWith("registry_configs/")),
      );
    }
  }, [detail.data?.content, selected]);

  const store = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("No config selected");
      return vtFetch("api/driver/config/store", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: selected, content: text, csv: isCsv }),
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["driver-config", selected] }),
  });

  const del = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("No config selected");
      return vtFetch("api/driver/config/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: selected }),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["driver-configs"] });
      setSelected(null);
      setText("");
    },
  });

  const grouped = useMemo(() => groupConfigs(list.data?.items ?? []), [list.data]);

  if (list.isLoading) return <Skeleton className="h-[520px] w-full rounded-xl" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Platform Driver configs</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tree of <code className="rounded bg-muted px-1">vctl config list platform.driver</code> entries.
          Edit JSON device configs (interval, BACnet address, registry path) or CSV registries (limits,
          scaling). After saving, restart <code className="rounded bg-muted px-1">platform.driver</code> from
          the System page.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardContent className="max-h-[560px] overflow-auto pt-6">
            {Object.entries(grouped).map(([group, names]) => (
              <div key={group} className="mb-4">
                <p className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase text-muted-foreground">
                  {group === "devices" ? (
                    <FileJson className="h-3.5 w-3.5" />
                  ) : group.startsWith("registry") ? (
                    <Table2 className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                  {group}
                </p>
                <ul className="space-y-0.5">
                  {names.map((n) => (
                    <li key={n}>
                      <button
                        type="button"
                        onClick={() => setSelected(n)}
                        className={`w-full rounded px-2 py-1 text-left text-xs font-mono hover:bg-muted ${
                          selected === n ? "bg-muted font-medium" : ""
                        }`}
                      >
                        {n}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="lg:col-span-3">
          <CardContent className="space-y-3 pt-6">
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm font-medium">{selected ?? "Select a config"}</p>
              <label className="flex items-center gap-2 text-xs">
                <input type="checkbox" checked={isCsv} onChange={(e) => setIsCsv(e.target.checked)} />
                Store as CSV (<code>--csv</code>)
              </label>
              <button
                type="button"
                disabled={!selected || store.isPending}
                className="rounded bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
                onClick={() => store.mutate()}
              >
                Save to config store
              </button>
              <button
                type="button"
                disabled={!selected || del.isPending}
                className="rounded border border-destructive px-3 py-1.5 text-xs text-destructive disabled:opacity-50"
                onClick={() => {
                  if (window.confirm(`Delete config "${selected}" from platform.driver?`)) del.mutate();
                }}
              >
                Delete…
              </button>
            </div>
            {detail.isFetching ? <Skeleton className="h-80 w-full" /> : null}
            <textarea
              className="min-h-[360px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={false}
            />
            {detail.data?.stderr ? (
              <pre className="rounded bg-destructive/10 p-2 text-xs">{detail.data.stderr}</pre>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
