#!/usr/bin/env bash
# Run on the Pi after deploy unzip so Docker build context can read every path (fixes
# "lstat .../bas/templates/bas: permission denied" when dirs were root-owned or not traversable).
set -u
DIR="${1:?usage: pi_post_unzip_fix.sh /home/user/diy-bas [username]}"
USER_NAME="${2:-$(id -un)}"
log() { echo "[pi_post_unzip_fix $(date -Iseconds)] $*"; }

log "DIR=$DIR TARGET_USER=$USER_NAME (remote_user=$(id -un))"
if [[ ! -d "$DIR" ]]; then
  log "ERROR: directory missing: $DIR"
  exit 1
fi

log "ls -la bas/templates (top):"
ls -la "$DIR/bas" 2>&1 || true
ls -la "$DIR/bas/templates" 2>&1 || true
ls -la "$DIR/bas/templates/bas" 2>&1 || true

log "paths not owned by $USER_NAME (first 25):"
find "$DIR" ! -user "$USER_NAME" 2>/dev/null | head -25 || true

log "paths not readable (first 15):"
find "$DIR" ! -readable 2>/dev/null | head -15 || true

if sudo -n true 2>/dev/null; then
  log "running: sudo chown -R $USER_NAME:$USER_NAME $DIR"
  sudo -n chown -R "$USER_NAME:$USER_NAME" "$DIR"
else
  log "running: chown -R $USER_NAME:$USER_NAME $DIR (no passwordless sudo — may not fix root-owned files)"
  chown -R "$USER_NAME:$USER_NAME" "$DIR" || log "WARN: chown failed (e.g. root-owned files). On the Pi run: sudo chown -R $USER_NAME:$USER_NAME $DIR"
fi

log "chmod: dirs u+rwx, files u+rw"
find "$DIR" -type d -exec chmod u+rwx {} \;
find "$DIR" -type f -exec chmod u+rw {} \;

log "after fix — bas/templates/bas:"
ls -la "$DIR/bas/templates/bas" 2>&1 || true
log "remaining wrong-owner (first 10, should be empty):"
find "$DIR" ! -user "$USER_NAME" 2>/dev/null | head -10 || true
log "done."
