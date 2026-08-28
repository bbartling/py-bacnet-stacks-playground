#!/usr/bin/env bash
# Run serial-wire-test with dialout when the current session lacks active group membership.
# Usage: launch_serial_wire_test.sh /path/to/serial-wire-test --port-a ... --port-b ...
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "usage: launch_serial_wire_test.sh BINARY [args...]" >&2
  exit 2
fi
BIN="$1"
shift

port_rw() {
  [[ -e "$1" ]] && python3 -c "import os,sys; sys.exit(0 if os.access(sys.argv[1], os.R_OK|os.W_OK) else 1)" "$1"
}

in_active_dialout() {
  id -nG | grep -qw dialout
}

member_of_dialout() {
  getent group dialout | grep -qw "${USER:-$(id -un)}"
}

# Extract ports from argv for access probe.
PORT_A=""
PORT_B=""
args=("$@")
i=0
while [[ $i -lt ${#args[@]} ]]; do
  case "${args[$i]}" in
    --port-a)
      PORT_A="${args[$((i + 1))]:-}"
      i=$((i + 2))
      ;;
    --port-b)
      PORT_B="${args[$((i + 1))]:-}"
      i=$((i + 2))
      ;;
    *)
      i=$((i + 1))
      ;;
  esac
done

if [[ -n "$PORT_A" && -n "$PORT_B" ]] && port_rw "$PORT_A" && port_rw "$PORT_B"; then
  exec "$BIN" "$@"
fi

if member_of_dialout; then
  cmd=$(printf '%q ' "$BIN" "$@")
  exec sg dialout -c "$cmd"
fi

echo "Serial ports not writable. Add user to dialout, then log in again:" >&2
echo "  sudo usermod -aG dialout \$USER" >&2
if [[ -n "$PORT_A" ]]; then
  echo "  Port A: $PORT_A (exists=$( [[ -e $PORT_A ]] && echo yes || echo no ))" >&2
fi
if [[ -n "$PORT_B" ]]; then
  echo "  Port B: $PORT_B (exists=$( [[ -e $PORT_B ]] && echo yes || echo no ))" >&2
fi
if in_active_dialout; then
  echo "  dialout is active but ports still denied — check udev/cable." >&2
fi
exit 1
