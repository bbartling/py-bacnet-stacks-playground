import { Card, CardContent } from "@/components/ui/card";

const CHEAT = String.raw`BAS Lite deployment + platform-driver notes

1) One-command bootstrap (Pi or Linux host — from this app root after git clone)
   cd /path/to/py-bacnet-stacks-playground/vibe_code_apps_8
   ./scripts/bootstrap-bas-lite.sh
   # does:
   # - cp .env.example .env (if needed)
   # - append bosspi.env once (LAN ports + BACNET_UDP_HOST_PORT=47809 fallback)
   # - generate BACNET_RPC_API_KEY if placeholder
   # - docker compose down && up -d

2) Verify runtime health
   docker compose ps
   docker compose logs -f caddy api diy-bacnet
   curl -sS http://127.0.0.1:18080/app8/api/health

3) LAN UI path
   http://PI_IP:18080/app8/
   # if refused: check caddy container is Up and port bind in .env:
   # CADDY_HTTP_PORTS=18080:80

4) BACnet JSON-RPC bearer key (diy-bacnet + easy-aso)
   grep BACNET_RPC_API_KEY .env
   # same key is used by both diy-bacnet service and api service

5) BACnet driver / point config storage
   docker compose exec api ls -la /data/driver_configs
   # JSON and CSV driver config files

6) Discovery export/import for AI-assisted modeling
   # export current discovered devices + points:
   curl -sS http://127.0.0.1:18080/app8/api/discovery/export | jq .
   # import edited JSON from LLM/OpenClaw workflow:
   curl -sS -X POST http://127.0.0.1:18080/app8/api/discovery/import \
     -H "Content-Type: application/json" \
     --data @edited_discovery.json

7) Alarms + trends + SD-card discipline
   # alarm definitions are JSON:
   curl -sS http://127.0.0.1:18080/app8/api/alarms/definitions
   # trends are ring-buffered in memory and sampled at BAS_LITE_TREND_SAMPLE_SEC.
   # long retention should be centralized off-Pi when possible.

8) SQLite + schedule
   docker compose exec api ls -la /data
   # supervisor.sqlite + schedule.json live here

9) Rebuild UI after edits (commit + pull on the host, or build locally)
   cd frontend && npm install && VITE_BASE_PATH=/app8 npm run build
   # set FRONTEND_SKIP_NODE_BUILD=1 in .env to bake dist into the nginx image, then:
   docker compose build frontend && docker compose up -d

10) Compose rebuild on the host
   docker compose build frontend --no-cache && docker compose up -d

11) Optional auth / TLS
   See docs/BOSS_PI_BAS_LITE_DOCKER.md and docker/caddy/Caddyfile.with-auth

Roadmap notes:
- BACnet + Modbus point trees should converge to one editable hierarchy in Live points.
- AI-assisted workflow: discovery export -> LLM edits polling/trending/alarm flags -> import -> operator review.
- Keep Faults and Alarms as separate tabs: Faults for diagnostics/rules, Alarms for actionable events.
`;

export function BasDocsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Deployment &amp; platform notes</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Docker + easy-aso operator notes, inspired by Open-FDD style bootstrap and docs workflows. Authoritative
          easy-aso docs:{" "}
          <a
            className="text-primary underline"
            href="https://bbartling.github.io/easy-aso/"
            target="_blank"
            rel="noreferrer"
          >
            bbartling.github.io/easy-aso
          </a>{" "}
          · Open-FDD references:{" "}
          <a
            className="text-primary underline"
            href="https://github.com/bbartling/open-fdd-afdd-stack/tree/main/docs"
            target="_blank"
            rel="noreferrer"
          >
            docs
          </a>{" "}
          and{" "}
          <a
            className="text-primary underline"
            href="https://github.com/bbartling/open-fdd-afdd-stack/tree/main/frontend"
            target="_blank"
            rel="noreferrer"
          >
            frontend
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
