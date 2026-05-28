#!/usr/bin/env bash
exec "$(dirname "$0")/_run_playbook.sh" validate_edge_iot.yml "$@"
