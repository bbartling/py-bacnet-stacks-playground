#!/usr/bin/env python3
"""Validate the shared-skill migration registry using only the standard library."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "agentic_ai" / "skills" / "migration_registry.json"


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    errors: list[str] = []
    migrations = registry.get("migrations", [])
    expected = registry.get("audit", {}).get("total_skill_files")
    if len(migrations) != expected:
        errors.append(f"registry has {len(migrations)} entries; expected {expected}")
    seen: set[str] = set()
    for item in migrations:
        source = item.get("source")
        if not isinstance(source, str) or not source:
            errors.append(f"invalid source: {item!r}")
            continue
        if source in seen:
            errors.append(f"duplicate source: {source}")
        seen.add(source)
        if not (ROOT / source).is_file():
            errors.append(f"missing source: {source}")
        targets = item.get("targets")
        status = item.get("status")
        if status == "promoted" and not targets:
            errors.append(f"promoted source has no shared target: {source}")
        if status not in {"promoted", "preserved_only"}:
            errors.append(f"invalid status for {source}: {status!r}")
        for target in targets or []:
            skill = ROOT / "agentic_ai" / "skills" / target / "SKILL.md"
            if not skill.is_file():
                errors.append(f"missing shared target for {source}: {target}")
    actual = sorted(
        str(path.relative_to(ROOT))
        for app in ("vibe_code_apps_19", "vibe_code_apps_20", "vibe_code_apps_21", "vibe_code_apps_22")
        for path in (ROOT / app).rglob("SKILL.md")
    )
    if sorted(seen) != actual:
        errors.append("registry source set does not match discovered Vibe 19-22 SKILL.md files")
    if errors:
        print("migration registry validation FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    promoted = sum(item["status"] == "promoted" for item in migrations)
    print(f"migration registry valid: {len(migrations)} sources; {promoted} promoted; {len(migrations) - promoted} preserved-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
