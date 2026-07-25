"""``wattlab`` command line — one front door for every workflow.

Subcommands delegate to the underlying module ``main(argv)`` functions so the
old script invocations (``python easy_button.py …``) and the packaged CLI stay
behaviour-identical.
"""

from __future__ import annotations

import sys


def _usage() -> str:
    return (
        "usage: wattlab <command> [args]\n"
        "\n"
        "commands:\n"
        "  twin         Turnkey: vibe19 dump -> gaps -> profile -> FDD bridge (start here)\n"
        "  defaults     Resolve a building profile from minimal inputs\n"
        "  easy-button  Baseline + measure-set EnergyPlus runs (or --dry-run plan)\n"
        "  calibrate    Calibrate prototype against a vibe19 model-seed bundle\n"
        "  calibrate-campaign  Bills→AMY window→G14 score→Twin publish (turnkey)\n"
        "  bridge       Map a vibe19 export bundle to WattLab measures\n"
        "  epw          Build an AMY EPW from observed weather CSV\n"
        "  bench        Deterministic proxy / ESCO bin-method calculators\n"
        "  crosscheck   Compare EnergyPlus savings vs bench/ESCO proxies\n"
        "  benchmark    Campus bill EUIs, allocation scenarios, peer-band compare\n"
        "  seed         Inspect a vibe19 WattLab dump (summary + gap report)\n"
        "               also: wattlab seed import-bills --electric CSV --gas CSV --out utility_bills.csv\n"
        "  studio-bootstrap  Write studio_bootstrap.json for Streamlit auto-load\n"
        "  studio-status     Merge dump/answers/bootstrap/run → session_status.json\n"
        "  geo-idf          Adapt DOE Large Office IDF → site-scale massing (any building)\n"
        "  dial-loads       Dial lights/equip/infil via EnergyPlus MCP (auto mcp-exec)\n"
        "  score-monthly    Score eplusout Monthly vs bills (last-12, area_scale=1)\n"
        "  energyplus-ensure  Clone pinned EnergyPlus-MCP + build energyplus-mcp-dev\n"
        "  mcp-exec         Run uv args inside energyplus-mcp-dev (IDF inspect/modify)\n"
        "  explore-existing  Existing Building Hypothesis Lab orchestration\n"
        "  hypothesis-lab    Alias for explore-existing\n"
        "  controls-checklist  vibe19 dump → controls FDD checklist (md/json/docx)\n"
        "  ecm          Canonical ECM catalog (list/describe/package/audit)\n"
        "  notebook     ECM engineering Excel notebooks (build/prefill/validate)\n"
        "  studio       Launch the WattLab Studio web app (Streamlit)\n"
    )


def _cmd_seed(argv: list[str]) -> int:
    import argparse
    import json
    import sys

    if argv and argv[0] == "import-bills":
        from wattlab.seed.import_bills import main as import_main

        return int(import_main(argv[1:]) or 0)

    p = argparse.ArgumentParser(prog="wattlab seed", description="Inspect a vibe19 WattLab dump")
    p.add_argument("path", help="dump folder or zip")
    p.add_argument("--gaps", action="store_true", help="print gap report instead of summary")
    p.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when any required gap is missing (for agent loops)",
    )
    args = p.parse_args(argv)

    from wattlab.seed import gap_report, load_bundle

    bundle = load_bundle(args.path)
    if args.gaps or args.strict:
        gaps = gap_report(bundle)
        print(json.dumps(gaps, indent=2, default=str))
        if args.strict and any(g.get("severity") == "required" and g.get("status") == "missing" for g in gaps):
            return 1
        return 0
    print(json.dumps(bundle.summary(), indent=2, default=str))
    return 0


def _cmd_benchmark(argv: list[str]) -> int:
    import argparse
    import json

    p = argparse.ArgumentParser(
        prog="wattlab benchmark",
        description="Annualize campus utility bills, run allocation scenarios, compare EUIs to peer bands",
    )
    p.add_argument("campus", help="campus.json describing buildings, meters and bill CSVs")
    p.add_argument("--allocation", default="area_weighted",
                   help="shared-meter split: area_weighted | equal | gas_share | manual")
    p.add_argument("--scenarios", action="store_true", help="print every allocation scenario side-by-side")
    args = p.parse_args(argv)

    from wattlab.benchmarks import Campus, allocation_scenarios, annual_summary, compare_eui

    campus = Campus.from_json(args.campus)
    if args.scenarios:
        print(json.dumps(allocation_scenarios(campus), indent=2))
        return 0
    summary = annual_summary(campus, allocation=args.allocation)
    for row in summary["buildings"]:
        row["benchmark"] = compare_eui(row["site_eui_kbtu_ft2"], row["property_type"])
    print(json.dumps(summary, indent=2))
    return 0


def _cmd_studio(argv: list[str]) -> int:
    import subprocess
    from pathlib import Path

    studio = Path(__file__).resolve().parents[1] / "studio.py"
    if not studio.is_file():
        print(f"studio app not found: {studio}", file=sys.stderr)
        return 2
    cmd = [sys.executable, "-m", "streamlit", "run", str(studio), *argv]
    return subprocess.call(cmd)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(_usage())
        return 0
    cmd, rest = args[0], args[1:]

    if cmd == "twin":
        from wattlab.twin import main as m

        return int(m(rest) or 0)
    if cmd == "defaults":
        from wattlab.defaults import main as m

        return int(m(rest) or 0)
    if cmd in {"easy-button", "easy_button"}:
        from wattlab.easy_button import main as m

        return int(m(rest) or 0)
    if cmd == "calibrate":
        from wattlab.calibrate import main as m

        return int(m(rest) or 0)
    if cmd in {"calibrate-campaign", "calibrate_campaign"}:
        from wattlab.calibrate_campaign import main as m

        return int(m(rest) or 0)
    if cmd == "bridge":
        from wattlab.bridge import main as m

        return int(m(rest) or 0)
    if cmd == "epw":
        from wattlab.weather.epw import main as m

        return int(m(rest) or 0)
    if cmd == "bench":
        from wattlab.bench.cli import main as m

        old_argv = sys.argv
        sys.argv = ["wattlab bench", *rest]
        try:
            return int(m() or 0)
        finally:
            sys.argv = old_argv
    if cmd == "crosscheck":
        from wattlab.crosscheck import main as m

        return int(m(rest) or 0)
    if cmd == "benchmark":
        return _cmd_benchmark(rest)
    if cmd == "seed":
        return _cmd_seed(rest)
    if cmd in {"studio-bootstrap", "studio_bootstrap"}:
        from wattlab.studio.bootstrap import main as m

        return int(m(rest) or 0)
    if cmd in {"studio-status", "studio_status"}:
        from wattlab.studio.status import main as m

        return int(m(rest) or 0)
    if cmd in {"geo-idf", "geo_idf"}:
        from wattlab.energyplus.geo_idf import main as m

        return int(m(rest) or 0)
    if cmd in {"dial-loads", "dial_loads"}:
        from wattlab.energyplus.dial_loads import main as m

        return int(m(rest) or 0)
    if cmd in {"score-monthly", "score_monthly"}:
        from wattlab.energyplus.score_monthly import main as m

        return int(m(rest) or 0)
    if cmd in {"energyplus-ensure", "energyplus_ensure"}:
        from wattlab.energyplus.mcp_runtime import main_ensure as m

        return int(m(rest) or 0)
    if cmd in {"mcp-exec", "mcp_exec"}:
        from wattlab.energyplus.mcp_runtime import main_mcp_exec as m

        return int(m(rest) or 0)
    if cmd in {"explore-existing", "hypothesis-lab"}:
        from wattlab.existing_building.cli import main as m

        return int(m(rest) or 0)
    if cmd in {"controls-checklist", "controls_checklist"}:
        from wattlab.existing_building.controls_checklist import main as m

        return int(m(rest) or 0)
    if cmd == "ecm":
        from wattlab.ecm.cli import main as m

        return int(m(rest) or 0)
    if cmd == "notebook":
        from wattlab.notebooks.cli import main as m

        return int(m(rest) or 0)
    if cmd == "studio":
        return _cmd_studio(rest)

    print(f"unknown command: {cmd!r}\n\n{_usage()}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
