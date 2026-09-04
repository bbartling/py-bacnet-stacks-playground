#!/usr/bin/env bash
# Build immutable release on the tower (or matching CI) for Pi deploy.
# Does not touch the tower's live BACnet service path.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIBE13="$(cd "$ROOT/../.." && pwd)"
REV="${1:?revision sha required}"
OUT="$ROOT/files/releases/$REV"
ARCH_TRIPLE="${PI_LAB_TARGET_TRIPLE:-aarch64-unknown-linux-gnu}"

mkdir -p "$OUT/bin" "$OUT/static"
cd "$VIBE13"

# Prefer cargo zigbuild / cross when available; fall back to native aarch64 host.
if command -v cross >/dev/null 2>&1; then
  cross build --release --locked --target "$ARCH_TRIPLE" \
    -p mstp-mini-device -p mstp-probe -p vibe13-observer -p vibe13-raw-peer
  BIN_DIR="target/$ARCH_TRIPLE/release"
elif [[ "$(uname -m)" == "aarch64" ]]; then
  cargo build --release --locked \
    -p mstp-mini-device -p mstp-probe -p vibe13-observer -p vibe13-raw-peer
  BIN_DIR="target/release"
else
  echo "Building x86_64 host bins for packaging smoke; set PI_LAB_TARGET_TRIPLE + cross for Pi." >&2
  cargo build --release --locked \
    -p mstp-mini-device -p mstp-probe -p vibe13-observer -p vibe13-raw-peer
  BIN_DIR="target/release"
fi

for b in mstp-mini-device mstp-probe vibe13-observer vibe13-raw-peer; do
  install -m 0755 "$BIN_DIR/$b" "$OUT/bin/$b"
done

if [[ -d "$VIBE13/apps/vibe13-observer/static" ]]; then
  cp -a "$VIBE13/apps/vibe13-observer/static/." "$OUT/static/"
fi

python3 - <<PY
import hashlib, json, pathlib, os, time
out = pathlib.Path("$OUT")
files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
lines = []
for p in files:
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    rel = p.relative_to(out).as_posix()
    lines.append(f"{h}  {rel}")
(out / "SHA256SUMS").write_text("\n".join(lines) + "\n")
manifest = {
    "schema": "vibe13_release_v1",
    "release_id": "$REV",
    "app_git_sha": "$REV",
    "upstream_sha": "af4e88680c51eb4da64dac47f0540a35bf184732",
    "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "host_arch": os.uname().machine,
    "target_triple": "$ARCH_TRIPLE",
    "binaries": ["mstp-mini-device", "mstp-probe", "vibe13-observer", "vibe13-raw-peer"],
}
(out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Built release at {out}")
PY
