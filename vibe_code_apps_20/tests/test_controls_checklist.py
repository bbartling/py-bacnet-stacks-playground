"""Controls checklist from synthetic vibe19 dump zips."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from wattlab.existing_building.controls_checklist import (
    build_report,
    load_dump,
    main,
    render_markdown,
)


def _zip_dump(path: Path, *, n_vav: int = 5, epidemic: bool = False) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        seed = {
            "display_name": "Test Building",
            "data_window": {"span_hours": 1000},
        }
        zf.writestr("model_seed.json", json.dumps(seed))
        comfort_rows = ["equipment_id,pct_outside_comfort,n_occupied,n_below,n_above,mean_zone_t,min_zone_t,max_zone_t,comfort_low_f,comfort_high_f,outlier"]
        for i in range(n_vav):
            comfort_rows.append(
                f"VAV-{i},10,100,5,5,72,70,74,70,75,False"
            )
        zf.writestr("rcx_zone_comfort_ranking.csv", "\n".join(comfort_rows) + "\n")
        fdd = [
            "equipment_id,equipment_type,rule_id,status,fault_hours,fault_pct,missing_roles,notes"
        ]
        # One real-ish fault
        fdd.append("VAV-0,VAV,VAV-4,FAULT,40,20,,")
        if epidemic:
            for i in range(n_vav):
                fdd.append(f"VAV-{i},VAV,VAV-5,FAULT,900,98,,")
        zf.writestr("fdd_summary.csv", "\n".join(fdd) + "\n")
        zf.writestr(
            "sensor_fault_summary.csv",
            "equipment_id,sensor,sensor_type,rule_id,fault_hours,mean,p50,min,max,fault_max\n",
        )
        zf.writestr(
            "sensor_stats_fan_off.csv",
            "equipment_id,role,units,p50,mean\nAHU-1,duct-static-pressure,in. w.c.,2.5,2.4\n",
        )
        zf.writestr(
            "sensor_stats_fan_on.csv",
            "equipment_id,role,units,p50,mean\nAHU-1,duct-static-pressure,in. w.c.,1.1,1.0\n",
        )
        zf.writestr("role_map_gap_report.csv", "equipment_id,missing_role\n")
    path.write_bytes(buf.getvalue())
    return path


def test_build_report_and_markdown(tmp_path: Path):
    z = _zip_dump(tmp_path / "wattlab_dump_test.zip")
    dump = load_dump(z)
    try:
        report = build_report(dump, in_band_min=80.0, fp_tuning_notes="Retuned VAV-5 gate")
    finally:
        dump["zf"].close()
    assert report["summary"]["n_vav"] == 5
    assert report["summary"]["n_fan_off_anomalies"] == 1
    assert report["fp_tuning_notes"]
    md = render_markdown(report)
    assert "Agent FDD false-positive tuning" in md
    assert "Retuned VAV-5 gate" in md


def test_epidemic_flags_agent_iterate(tmp_path: Path):
    z = _zip_dump(tmp_path / "wattlab_dump_epi.zip", epidemic=True)
    dump = load_dump(z)
    try:
        report = build_report(dump, in_band_min=80.0)
    finally:
        dump["zf"].close()
    unusual = report["unusual_faults"]
    assert unusual["agent_should_iterate_vibe19"] is True
    assert "VAV-5" in unusual["epidemic_vav_rules"]
    md = render_markdown(report)
    assert "excessively high" in md.lower() or "iterate vibe19" in md.lower()


def test_cli_writes_outputs(tmp_path: Path):
    z = _zip_dump(tmp_path / "wattlab_dump_cli.zip")
    out = tmp_path / "out"
    rc = main(
        [
            "--dump",
            str(z),
            "--out-dir",
            str(out),
            "--fp-tuning-note",
            "before 10 FAULTs → after 2",
        ]
    )
    assert rc == 0
    md_files = list(out.glob("*_checklist.md"))
    json_files = list(out.glob("*_checklist.json"))
    assert len(md_files) == 1 and len(json_files) == 1
    text = md_files[0].read_text(encoding="utf-8")
    assert "before 10 FAULTs" in text
