import { Card, CardContent } from "@/components/ui/card";

const CHEAT = String.raw`BAS Lite — Docker + modular VOLTTRON (edge)

Assumptions: docker compose up on the Pi; Caddy on :80/:443; App 8 web agent exposed through VOLTTRON web.

1) Check platform + web agent
   docker compose ps
   docker compose logs -f volttron
   curl -sS http://127.0.0.1:8080/app8/api/health

2) VOLTTRON agent/runtime status
   docker compose exec volttron vctl status
   docker compose exec volttron vctl auth list

3) SPA JSON API
   curl -sS http://PI_IP/app8/api/health
   curl -sS http://PI_IP/app8/api/points

4) Driver config files
   curl -sS http://PI_IP/app8/api/driver/configs
   docker compose exec volttron vctl config list platform.driver

5) Schedule store
   curl -sS http://PI_IP/app8/api/schedule

6) Rebuild UI after React edits
   ./rebuild-bas-lite.sh --rebuild-frontend

7) Optional auth / TLS
   See docs/bas-lite-app8-tutorial.md and docker/caddy/Caddyfile

8) BACnet networking fallback
   For broadcast/routing issues on Linux:
   docker compose -f docker-compose.yml -f docker-compose.hostnet.yml up -d
`;

export function BasDocsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">BACnet &amp; driver cheat sheet</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Docker + modular VOLTTRON operator notes. App 8 web agent API lives under{" "}
          <code className="rounded bg-muted px-1">/app8/api/*</code>.
        </p>
      </div>
      <Card>
        <CardContent className="pt-6">
          <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-4 font-mono text-xs leading-relaxed">
            {CHEAT}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
