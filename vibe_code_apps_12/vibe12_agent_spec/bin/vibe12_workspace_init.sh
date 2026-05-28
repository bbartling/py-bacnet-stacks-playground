#!/usr/bin/env bash
# Initialize local agent workspace after git clone (memory + checkpoints not in repo).
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC="$(cd "$BIN_DIR/.." && pwd)"
TEMPLATES="$SPEC/templates"
FORCE=false

if [[ "${1:-}" == "--force" ]]; then
  FORCE=true
fi

copy_if_missing() {
  local src="$1" dst="$2"
  if [[ -f "$dst" && "$FORCE" != "true" ]]; then
    echo "  skip (exists): $dst"
    return 0
  fi
  mkdir -p "$(dirname "$dst")"
  cp -f "$src" "$dst"
  echo "  wrote: $dst"
}

echo "=== vibe12 workspace init ==="
echo "SPEC=$SPEC"

copy_if_missing "$TEMPLATES/MEMORY.md.example" "$SPEC/MEMORY.md"
copy_if_missing "$TEMPLATES/BUILD_CHECKPOINTS.example.md" "$SPEC/BUILD_CHECKPOINTS.md"
copy_if_missing "$TEMPLATES/memo../edge_backup/PHASE_NOTEPAD.example.md" \
  "$SPEC/memo../edge_backup/PHASE_NOTEPAD.md"
copy_if_missing "$TEMPLATES/memory/integrations/aws-iot.example.md" \
  "$SPEC/memory/integrations/aws-iot.md"
copy_if_missing "$TEMPLATES/memory/stack/edge-gateway.example.md" \
  "$SPEC/memory/stack/edge-gateway.md"
copy_if_missing "$TEMPLATES/memory/stack/cloud-deploy.example.md" \
  "$SPEC/memory/stack/cloud-deploy.md"
copy_if_missing "$TEMPLATES/memory/sites/site-building.example.md" \
  "$SPEC/memory/sites/site-building.md"
copy_if_missing "$TEMPLATES/memory/architecture/working-divergence.example.md" \
  "$SPEC/memory/architecture/working-divergence.md"

TODAY="$(date -u +%Y-%m-%d)"
copy_if_missing "$TEMPLATES/memory/daily.example.md" "$SPEC/memory/${TODAY}.md"

mkdir -p "$SPEC/scratch" "$SPEC/cron_codex/logs" "$SPEC/cron_codex/state"
copy_if_missing "$TEMPLATES/cron_codex/state/operator_notes.example.md" \
  "$SPEC/cron_codex/state/operator_notes.md"
copy_if_missing "$TEMPLATES/cron_codex/state/next_directions.example.md" \
  "$SPEC/cron_codex/state/next_directions.md"

if [[ ! -f "$SPEC/cron_codex/.env" ]]; then
  cp -f "$SPEC/cron_codex/env.example" "$SPEC/cron_codex/.env"
  echo "  wrote: cron_codex/.env (from env.example)"
else
  echo "  skip (exists): cron_codex/.env"
fi

"$BIN_DIR/vibe12_workspace_cli.sh" memory write-bootstrap 2>/dev/null || true

cat <<EOF

Next steps:
  1. codex login
  2. Edit memo../edge_backup/PHASE_NOTEPAD.md for your site
  3. cp aws_cloud_pipeline/samconfig.toml.example → samconfig.toml (cloud deploy)
  4. See docs/agent-getting-started.md

Cron (optional, after testing): cron_codex/bin/vibe12_install_cron.sh --yes
EOF
