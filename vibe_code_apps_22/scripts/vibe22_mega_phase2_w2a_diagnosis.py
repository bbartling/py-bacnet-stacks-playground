"""CLI: Phase 2 W2A diagnosis with MCP evidence (fail-closed)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.phase2_w2a_diagnosis import build_w2a_diagnosis, write_phase2_artifacts


def main() -> int:
    p = argparse.ArgumentParser(description="Vibe22 mega Phase 2 W2A diagnosis")
    p.add_argument("--idf", type=Path, default=_APP / "models" / "eplus" / A04_IDF_NAME)
    p.add_argument(
        "--json-out",
        type=Path,
        default=_APP / "docs" / "audits" / "figures" / "vibe22_mega_phase2" / "phase2_w2a_diagnosis.json",
    )
    p.add_argument(
        "--md-out",
        type=Path,
        default=_APP / "docs" / "audits" / "2026-08-19-vibe22-mega-phase2-w2a-diagnosis.md",
    )
    p.add_argument(
        "--phase1-freeze",
        type=Path,
        default=_APP / "docs" / "audits" / "figures" / "vibe22_mega_phase1" / "phase1_evidence_freeze.json",
    )
    p.add_argument("--mcp-load", type=Path, required=True, help="JSON from load_idf_model MCP call")
    p.add_argument("--mcp-summary", type=Path, required=True, help="JSON from get_model_summary MCP call")
    p.add_argument("--mcp-hvac", type=Path, required=True, help="JSON from discover_hvac_loops MCP call")
    p.add_argument("--allow-no-mcp", action="store_true", help="Test only — skips MCP completeness gate")
    args = p.parse_args()

    phase1 = json.loads(args.phase1_freeze.read_text(encoding="utf-8")) if args.phase1_freeze.is_file() else None
    mcp_load = json.loads(args.mcp_load.read_text(encoding="utf-8"))
    mcp_summary = json.loads(args.mcp_summary.read_text(encoding="utf-8"))
    mcp_hvac = json.loads(args.mcp_hvac.read_text(encoding="utf-8"))

    diagnosis = build_w2a_diagnosis(
        idf_path=args.idf,
        mcp_load_result=mcp_load,
        mcp_model_summary=mcp_summary,
        mcp_hvac_loops=mcp_hvac,
        phase1_freeze=phase1,
        require_mcp=not args.allow_no_mcp,
    )
    write_phase2_artifacts(diagnosis, json_out=args.json_out, md_out=args.md_out)
    print(
        json.dumps(
            {
                "diagnosis_sha256": diagnosis["diagnosis_sha256"],
                "conclusion_strength": diagnosis["conclusion_strength"],
                "mcp_tools": diagnosis["mcp_inspection"]["mcp_tools_invoked"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
