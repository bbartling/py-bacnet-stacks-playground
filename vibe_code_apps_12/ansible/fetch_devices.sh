#!/usr/bin/env bash
# Fetch only devices_discovered.csv (fresh SSH). Use after discover_devices.sh completes.
exec "$(dirname "$0")/_run_playbook.sh" wait_fetch_devices.yml "$@"
