#!/usr/bin/env bash
exec "$(dirname "$0")/_run_playbook.sh" backup_registry.yml "$@"
