#!/usr/bin/env bash
exec "$(dirname "$0")/_run_playbook.sh" push_devices_csv.yml "$@"
