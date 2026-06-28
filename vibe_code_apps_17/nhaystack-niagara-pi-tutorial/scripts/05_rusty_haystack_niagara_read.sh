#!/usr/bin/env bash
# Run rusty-haystack niagara-read against the same station (optional fork checkout).
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f ".env" ]]; then
  # shellcheck disable=SC1091
  source ".env"
fi

RUSTY_ROOT="${RUSTY_HAYSTACK_ROOT:-$HOME/rusty-haystack}"

if [[ ! -f "$RUSTY_ROOT/Cargo.toml" ]]; then
  echo "Clone bbartling/rusty-haystack fork (AuthMode::Basic) first:"
  echo "  git clone https://github.com/bbartling/rusty-haystack.git \"$RUSTY_ROOT\""
  exit 1
fi

export HAYSTACK_BASE="${HAYSTACK_BASE:-https://${JACE_HOST:-192.168.204.11}/haystack}"

echo "Using rusty-haystack at $RUSTY_ROOT"
cd "$RUSTY_ROOT"
cargo run -p niagara-read -- \
  --url "$HAYSTACK_BASE" \
  --user "${HAYSTACK_USER:?}" \
  --password "${HAYSTACK_PASS:?}" \
  --auth basic \
  --probe-scram \
  --filter "point and cur"
