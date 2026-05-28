#!/usr/bin/env bash
exec "$(dirname "$0")/_run_playbook.sh" wait_fetch_devices.yml "$@"
