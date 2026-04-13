import { Card, CardContent } from "@/components/ui/card";

const CHEAT = String.raw`BAS Lite — Docker + easy-aso (edge)

Assumptions: docker compose up on the Pi; Caddy on :80; API uses SUPERVISOR_BACNET_RPC_URL for diy-bacnet JSON-RPC.

1) Check API + BACnet RPC
   docker compose ps
   docker compose logs -f api
   curl -sS http://127.0.0.1:8080/health    # on Pi host if diy-bacnet listens here

2) easy-aso supervisor (CRUD devices / points)
   curl -sS http://127.0.0.1/api/v1/health   # through Caddy from another machine use http://PI_IP/api/v1/health
   curl -sS http://PI_IP/openapi.json        # machine-readable OpenAPI (Swagger: port-forward to api:8090 /docs)

3) Legacy SPA JSON (same contract as old /app8/api)
   curl -sS http://PI_IP/app8/api/health

4) Driver config files (volume /data/driver_configs in api container)
   docker compose exec api ls -la /data/driver_configs

5) SQLite + schedule
   docker compose exec api ls -la /data
   # supervisor.sqlite + schedule.json live here

6) Rebuild UI after React edits
   docker compose build frontend --no-cache && docker compose up -d

7) SD card / logs
   docker compose uses capped log drivers; docker system prune occasionally

8) Optional auth / TLS
   See docs/BOSS_PI_BAS_LITE_DOCKER.md and docker/caddy/Caddyfile.with-auth

Notes: BACnet/IP UDP still belongs on the host or a dedicated container with host networking — this stack focuses on HTTP + JSON-RPC to your BACnet gateway.
`;

export function BasDocsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">BACnet &amp; driver cheat sheet</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Docker + easy-aso operator notes. Authoritative easy-aso docs:{" "}
          <a
            className="text-primary underline"
            href="https://bbartling.github.io/easy-aso/"
            target="_blank"
            rel="noreferrer"
          >
            bbartling.github.io/easy-aso
          </a>
          .
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
