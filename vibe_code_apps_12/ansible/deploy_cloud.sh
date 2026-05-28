#!/usr/bin/env bash
# SAM deploy from bensserver (AWS credentials required). Does not touch edge gateways.
exec "$(dirname "$0")/_run_playbook.sh" deploy_cloud.yml "$@"
