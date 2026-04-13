import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { vtFetch } from "@/lib/volttron-fetch";

type Event = {
  id: string;
  severity: string;
  state: string;
  message: string;
  triggeredAt: string;
  deviceId: string;
  pointId: string;
};

export function BasFaultsPage() {
  const events = useQuery({
    queryKey: ["bas-alarm-events"],
    queryFn: () => vtFetch<{ items: Event[] }>("api/alarms/events"),
    refetchInterval: 5000,
  });

  if (events.isLoading) return <Skeleton className="h-64 w-full rounded-xl" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Faults &amp; alarms</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Derived alarm state from live BACnet values (bench logic mirrors App 7).
        </p>
      </div>
      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Severity</TableHead>
                <TableHead>Message</TableHead>
                <TableHead>Point</TableHead>
                <TableHead>When</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(events.data?.items.length ? events.data.items : []).map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="text-xs font-medium uppercase">{e.severity}</TableCell>
                  <TableCell className="text-sm">{e.message}</TableCell>
                  <TableCell className="font-mono text-xs">{e.pointId}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{e.triggeredAt}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {!events.data?.items.length ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No active alarm events.</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
