#!/usr/bin/env bash
exec "$(dirname "$0")/_run_playbook.sh" discover_points.yml "$@"
