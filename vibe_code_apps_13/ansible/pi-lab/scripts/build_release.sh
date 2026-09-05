#!/usr/bin/env bash
# Build immutable AArch64 release for Pi deploy. No x86 packaging fallback.
# Does not touch the tower's live BACnet service path.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIBE13="$(cd "$ROOT/../.." && pwd)"
REV="${1:?revision sha (full 40-char) required}"
OUT="$ROOT/files/releases/$REV"
ARCH_TRIPLE="${PI_LAB_TARGET_TRIPLE:-aarch64-unknown-linux-gnu}"

python3 "$ROOT/scripts/lab_ids.py" check-run-id "$REV" >/dev/null
# Prefer full git SHA for releases
if [[ ! "$REV" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "ERROR: release id must be full 40-char git SHA (got $REV)" >&2
  exit 2
fi

HEAD="$(git -C "$VIBE13" rev-parse HEAD)"
if [[ "$HEAD" != "$REV" ]]; then
  echo "ERROR: requested revision $REV != checked-out HEAD $HEAD" >&2
  echo "Checkout the tested commit before packaging; never package dirty/arbitrary trees." >&2
  exit 2
fi
if [[ -n "$(git -C "$VIBE13" status --porcelain)" ]]; then
  echo "ERROR: working tree dirty — refuse to package under $REV" >&2
  exit 2
fi

rm -rf "$OUT"
mkdir -p "$OUT/bin" "$OUT/static"
cd "$VIBE13"

if command -v cross >/dev/null 2>&1; then
  cross build --release --locked --target "$ARCH_TRIPLE" \
    -p mstp-mini-device -p mstp-probe -p vibe13-observer -p vibe13-raw-peer
  BIN_DIR="target/$ARCH_TRIPLE/release"
elif [[ "$(uname -m)" == "aarch64" ]]; then
  cargo build --release --locked \
    -p mstp-mini-device -p mstp-probe -p vibe13-observer -p vibe13-raw-peer
  BIN_DIR="target/release"
else
  echo "ERROR: AArch64 cross/native build required. Install cross or build on aarch64." >&2
  echo "Refusing to package x86_64 host binaries for Pi deploy." >&2
  exit 2
fi

elf_is_aarch64() {
  local f="$1"
  # ELF e_machine EM_AARCH64 = 183 (0xB7) at offset 18 little-endian
  python3 - "$f" <<'PY'
import struct,sys
p=sys.argv[1]
with open(p,'rb') as fh:
    hdr=fh.read(20)
if hdr[:4]!=b'\x7fELF':
    raise SystemExit(f'not ELF: {p}')
machine=struct.unpack_from('<H', hdr, 18)[0]
if machine!=183:
    raise SystemExit(f'ELF machine {machine} != AArch64(183): {p}')
print('ok', p)
PY
}

for b in mstp-mini-device mstp-probe vibe13-observer vibe13-raw-peer; do
  install -m 0755 "$BIN_DIR/$b" "$OUT/bin/$b"
  elf_is_aarch64 "$OUT/bin/$b"
done

if [[ -d "$VIBE13/apps/vibe13-observer/static" ]]; then
  cp -a "$VIBE13/apps/vibe13-observer/static/." "$OUT/static/"
fi

python3 - <<PY
import hashlib, json, pathlib, os, time
out = pathlib.Path("$OUT")
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
# Hash AFTER writing MANIFEST so the ledger covers it.
files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
lines = []
for p in files:
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    rel = p.relative_to(out).as_posix()
    lines.append(f"{h}  {rel}")
(out / "SHA256SUMS").write_text("\n".join(lines) + "\n")
print(f"Built release at {out}")
PY
