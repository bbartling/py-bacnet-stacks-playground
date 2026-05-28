#!/usr/bin/env bash
exec "$(dirname "$0")/_run_playbook.sh" enable_read_driver.yml "$@"
