from __future__ import annotations

from vibe23.compute import CampaignCompute, PerRunTelemetry, collect_host_info, write_host_json


def test_host_info_and_campaign_summary(tmp_path):
    info = collect_host_info()
    assert "python_version" in info
    path = write_host_json(tmp_path / "host.json", info)
    assert path.is_file()
    runs = [
        PerRunTelemetry("a", 10.0, 0),
        PerRunTelemetry("b", 20.0, 0),
        PerRunTelemetry("c", 30.0, 0),
    ]
    summary = CampaignCompute(runs=runs, campaign_wall_seconds=30.0).summary()
    assert summary["aggregate_process_seconds"] == 60.0
    assert summary["wall_p50"] == 20.0
