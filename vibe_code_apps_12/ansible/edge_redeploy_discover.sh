#!/usr/bin/env bash
# Fresh edge install + foreground device discover + fetch (e.g. after rm -rf on gateway).
#
#   ./edge_redeploy_discover.sh --limit <inventory_host> -v
exec "$(dirname "$0")/edge_phase1_devices.sh" --skip-backup --foreground "$@"
