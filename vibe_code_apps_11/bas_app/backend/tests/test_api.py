from fastapi.testclient import TestClient
from datetime import datetime

from app.auth import issue_token
from app.main import app


client = TestClient(app)


def _login(username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_demo_site_endpoint_contains_seeded_hierarchy():
    response = client.get("/api/demo/site")
    assert response.status_code == 200
    payload = response.json()

    assert payload["id"] == "site-1"
    equipment = payload["buildings"][0]["floors"][0]["equipment"]
    assert {item["equipment_type"] for item in equipment} >= {"AHU", "VAV", "Lighting Panel"}
    points = [point for item in equipment for point in item["points"]]
    assert len(points) >= 10
    assert any(point["is_commandable"] for point in points)


def test_demo_navigation_endpoint_summarizes_site():
    response = client.get("/api/demo/navigation")
    assert response.status_code == 200
    payload = response.json()

    assert payload["site"]["id"] == "site-1"
    assert payload["summary"]["equipment_count"] == 3
    assert payload["summary"]["trended_point_count"] >= 10
    assert payload["buildings"][0]["floors"][0]["equipment"][0]["point_count"] >= 1


def test_demo_data_sweep_endpoint_returns_happy_path_summary():
    response = client.get("/api/demo/data-sweep")
    assert response.status_code == 200
    payload = response.json()

    assert payload["site"]["id"] == "site-1"
    assert payload["building"]["id"] == "bldg-1"
    assert payload["floor"]["id"] == "floor-1"
    assert payload["equipment"]["id"] == "eq-ahu-1"
    assert payload["equipment"]["point_count"] == 6
    assert payload["points"]["count"] == 6
    assert payload["points"]["ids"][0] == "pt-sat"
    assert "pt-sa-sp" in payload["points"]["ids"]
    assert payload["point_detail"]["id"] == "pt-sa-sp"
    assert payload["point_detail"]["source_protocol"] == "simulator"
    assert payload["point_detail"]["source_address"] == "sim://eq-ahu-1/pt-sa-sp"


def test_equipment_detail_and_points_endpoints():
    detail_response = client.get("/api/equipment/eq-ahu-1")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["name"] == "AHU-1"
    assert detail["point_count"] == 6

    points_response = client.get("/api/equipment/eq-ahu-1/points")
    assert points_response.status_code == 200
    points = points_response.json()
    assert len(points) == 6
    assert all("last_updated" in point for point in points)


def test_point_detail_endpoint_includes_equipment_context():
    response = client.get("/api/points/pt-sa-sp")
    assert response.status_code == 200
    payload = response.json()

    assert payload["id"] == "pt-sa-sp"
    assert payload["equipment"]["id"] == "eq-ahu-1"
    assert payload["source_protocol"] == "simulator"
    assert payload["is_trended"] is True
    assert payload["command_roles"] == ["Admin", "Engineer", "Operator"]
    assert payload["permission_summary"]["operator"] == "Can command"


def test_unknown_equipment_returns_404():
    response = client.get("/api/equipment/does-not-exist")
    assert response.status_code == 404


def test_unknown_point_returns_404():
    response = client.get("/api/points/does-not-exist")
    assert response.status_code == 404


def test_trend_points_endpoint_lists_only_trended_points():
    response = client.get("/api/trends/points")
    assert response.status_code == 200
    payload = response.json()

    points = payload["points"]
    assert len(points) >= 10
    assert {point["id"] for point in points} >= {"pt-sat", "pt-sa-sp", "pt-zone-temp"}
    assert all(point["source_protocol"] == "simulator" for point in points)
    assert all(point["id"] != "pt-light-override" for point in points)


def test_trend_samples_endpoint_returns_multi_point_history():
    response = client.get("/api/trends/samples", params={"point_ids": "pt-sat,pt-sa-sp", "hours": 4})
    assert response.status_code == 200
    payload = response.json()

    assert payload["window_hours"] == 4
    assert payload["interval_minutes"] == 30
    assert [point["id"] for point in payload["points"]] == ["pt-sat", "pt-sa-sp"]

    samples = payload["samples"]
    assert len(samples) >= 2
    assert {sample["point_id"] for sample in samples} == {"pt-sat", "pt-sa-sp"}
    assert all("timestamp" in sample for sample in samples)
    assert all("value" in sample for sample in samples)
    assert all(sample["quality"] == "good" for sample in samples)
    assert all(sample["status"] == "good" for sample in samples)


def test_trend_samples_reject_unknown_point():
    response = client.get("/api/trends/samples", params={"point_ids": "does-not-exist", "hours": 4})
    assert response.status_code == 404


def test_trend_samples_reject_non_trended_point():
    response = client.get("/api/trends/samples", params={"point_ids": "pt-light-override", "hours": 4})
    assert response.status_code == 400


def test_trend_samples_reject_out_of_range_hours():
    response = client.get("/api/trends/samples", params={"point_ids": "pt-sat", "hours": 25})
    assert response.status_code == 400
    assert "between 1 and 24" in response.json()["detail"]


def test_trend_csv_export_has_stable_headers_and_rows():
    response = client.get("/api/trends/export.csv", params={"point_ids": "pt-sat,pt-sa-sp", "hours": 4})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="bas-trends.csv"'

    lines = response.text.splitlines()
    assert lines[0] == "point_id,display_name,equipment_id,equipment_name,units,timestamp,value,quality,status"
    assert len(lines) > 2


def test_alarm_active_endpoint_returns_seeded_records():
    response = client.get("/api/alarms/active")
    assert response.status_code == 200
    payload = response.json()

    items = payload["items"]
    assert [item["alarm_id"] for item in items] == ["alm-sat-high", "alm-zone-temp-low", "alm-light-mismatch"]
    assert all(item["state"] == "active" for item in items)
    assert items[1]["acknowledged_timestamp"] == "2026-05-10T03:14:00+00:00"
    assert items[2]["shelved_until"] == "2026-05-10T04:22:00+00:00"


def test_alarm_history_endpoint_returns_resolved_records():
    response = client.get("/api/alarms/history")
    assert response.status_code == 200
    payload = response.json()

    items = payload["items"]
    assert [item["alarm_id"] for item in items] == ["alm-fan-fault-cleared", "alm-mixed-air-stale"]
    assert all(item["state"] == "resolved" for item in items)
    assert all(item["returned_to_normal_timestamp"] for item in items)


def test_alarm_csv_export_has_stable_headers_and_rows():
    response = client.get("/api/alarms/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="bas-alarms.csv"'

    lines = response.text.splitlines()
    assert lines[0] == (
        "alarm_id,point_id,equipment_id,alarm_type,severity,state,message,active_timestamp,"
        "acknowledged_timestamp,returned_to_normal_timestamp,acknowledged_by,shelved_until,operator_message"
    )
    assert any(line.startswith("alm-sat-high,pt-sat,eq-ahu-1,analog_high,high,active,Supply air temperature high,") for line in lines[1:])
    assert len(lines) > 2


def test_alarm_ack_requires_authentication():
    response = client.post(
        "/api/alarms/alm-sat-high/ack",
        json={"reason": "test"},
    )
    assert response.status_code == 401


def test_alarm_ack_rejects_read_only_user():
    token = _login("readonly", "readonly123")
    response = client.post(
        "/api/alarms/alm-sat-high/ack",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test"},
    )
    assert response.status_code == 403

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert events[0]["action_type"] == "alarm.ack"
    assert events[0]["username"] == "readonly"
    assert events[0]["result"] == "failure"
    assert events[0]["reason"] == "read_only_role"


def test_alarm_ack_rejects_missing_reason():
    token = _login("operator", "operator123")
    response = client.post(
        "/api/alarms/alm-sat-high/ack",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 400

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert events[0]["action_type"] == "alarm.ack"
    assert events[0]["username"] == "operator"
    assert events[0]["result"] == "failure"
    assert events[0]["reason"] == "reason_required"


def test_alarm_shelve_rejects_read_only_user():
    token = _login("readonly", "readonly123")
    response = client.post(
        "/api/alarms/alm-light-mismatch/shelve",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test"},
    )
    assert response.status_code == 403

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert events[0]["action_type"] == "alarm.shelve"
    assert events[0]["username"] == "readonly"
    assert events[0]["result"] == "failure"
    assert events[0]["reason"] == "read_only_role"


def test_alarm_shelve_rejects_missing_reason():
    token = _login("operator", "operator123")
    response = client.post(
        "/api/alarms/alm-light-mismatch/shelve",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 400

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert events[0]["action_type"] == "alarm.shelve"
    assert events[0]["username"] == "operator"
    assert events[0]["result"] == "failure"
    assert events[0]["reason"] == "reason_required"


def test_operator_alarm_ack_updates_state_and_audit():
    token = _login("operator", "operator123")
    response = client.post(
        "/api/alarms/alm-sat-high/ack",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Checked against occupied schedule"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["alarm_id"] == "alm-sat-high"
    assert payload["acknowledged_by"] == "operator"
    assert payload["operator_message"] == "Checked against occupied schedule"
    assert payload["state"] == "active"
    assert payload["acknowledged_timestamp"]

    timestamp = datetime.fromisoformat(payload["acknowledged_timestamp"])
    assert timestamp.tzinfo is not None

    active_response = client.get("/api/alarms/active")
    assert active_response.status_code == 200
    active_items = active_response.json()["items"]
    assert active_items[0]["acknowledged_by"] == "operator"
    assert active_items[0]["operator_message"] == "Checked against occupied schedule"

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert events[0]["action_type"] == "alarm.ack"
    assert events[0]["username"] == "operator"
    assert events[0]["target_id"] == "alm-sat-high"
    assert events[0]["reason"] == "Checked against occupied schedule"


def test_operator_alarm_shelve_updates_state_and_audit():
    token = _login("operator", "operator123")
    response = client.post(
        "/api/alarms/alm-light-mismatch/shelve",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Shelved during maintenance window"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["alarm_id"] == "alm-light-mismatch"
    assert payload["acknowledged_by"] == "operator"
    assert payload["operator_message"] == "Shelved during maintenance window"
    assert payload["shelved_until"]

    shelved_until = datetime.fromisoformat(payload["shelved_until"])
    acknowledged_at = datetime.fromisoformat(payload["acknowledged_timestamp"])
    assert shelved_until > acknowledged_at

    active_response = client.get("/api/alarms/active")
    assert active_response.status_code == 200
    active_items = active_response.json()["items"]
    shelved_alarm = next(item for item in active_items if item["alarm_id"] == "alm-light-mismatch")
    assert shelved_alarm["shelved_until"] == payload["shelved_until"]

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert events[0]["action_type"] == "alarm.shelve"
    assert events[0]["username"] == "operator"
    assert events[0]["target_id"] == "alm-light-mismatch"
    assert events[0]["reason"] == "Shelved during maintenance window"


def test_login_success_returns_token_and_user_profile():
    response = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "operator123"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["token_type"] == "bearer"
    assert payload["user"] == {
        "username": "operator",
        "full_name": "Demo Operator",
        "role": "Operator",
    }
    assert payload["access_token"]


def test_login_failure_rejects_bad_password():
    response = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "wrong"},
    )
    assert response.status_code == 401


def test_audit_events_endpoint_starts_empty():
    token = issue_token("operator")
    response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_login_attempts_are_recorded_in_audit_log():
    success_response = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "operator123"},
    )
    assert success_response.status_code == 200

    failure_response = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "wrong"},
    )
    assert failure_response.status_code == 401

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {success_response.json()['access_token']}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]

    assert len(events) == 2
    assert events[0]["action_type"] == "auth.login"
    assert events[0]["username"] == "operator"
    assert events[0]["result"] == "failure"
    assert events[0]["reason"] == "invalid_credentials"
    assert events[0]["timestamp"]
    assert events[1]["action_type"] == "auth.login"
    assert events[1]["username"] == "operator"
    assert events[1]["result"] == "success"
    assert events[1]["reason"] == "token_issued"
    assert events[1]["timestamp"]


def test_audit_events_requires_valid_bearer_token():
    missing_response = client.get("/api/audit/events")
    assert missing_response.status_code == 401

    response = client.get("/api/audit/events", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401

    token = issue_token("operator")
    authorized_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert authorized_response.status_code == 200
    assert authorized_response.json() == {"items": []}


def test_auth_me_requires_valid_bearer_token():
    missing_response = client.get("/api/auth/me")
    assert missing_response.status_code == 401

    login_response = client.post(
        "/api/auth/login",
        json={"username": "readonly", "password": "readonly123"},
    )
    token = login_response.json()["access_token"]

    me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json() == {
        "user": {
            "username": "readonly",
            "full_name": "Demo Read Only",
            "role": "ReadOnly",
        }
    }


def test_auth_me_rejects_invalid_token():
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_summary_endpoint_requires_valid_bearer_token():
    missing_response = client.get("/api/summary")
    assert missing_response.status_code == 401

    invalid_response = client.get("/api/summary", headers={"Authorization": "Bearer not-a-real-token"})
    assert invalid_response.status_code == 401

    token = _login("operator", "operator123")
    authorized_response = client.get("/api/summary", headers={"Authorization": f"Bearer {token}"})
    assert authorized_response.status_code == 200
    payload = authorized_response.json()

    assert payload["user"] == {
        "username": "operator",
        "full_name": "Demo Operator",
        "role": "Operator",
    }
    assert payload["site"] == {
        "id": "site-1",
        "name": "GL36 Demo Campus",
        "description": "Seeded BAS demo site with simulator-backed live values.",
        "address": "100 Main St, Demo City",
        "timezone": "America/Denver",
    }
    assert payload["summary"]["building_count"] == 1
    assert payload["summary"]["equipment_count"] == 3
    assert payload["summary"]["point_count"] >= 10
    assert payload["summary"]["active_alarm_count"] >= 1
    assert payload["summary"]["recent_audit_event_count"] >= 0


def test_schedules_endpoint_requires_valid_bearer_token():
    missing_response = client.get("/api/schedules")
    assert missing_response.status_code == 401

    invalid_response = client.get("/api/schedules", headers={"Authorization": "Bearer not-a-real-token"})
    assert invalid_response.status_code == 401

    token = _login("operator", "operator123")
    authorized_response = client.get("/api/schedules", headers={"Authorization": f"Bearer {token}"})
    assert authorized_response.status_code == 200
    payload = authorized_response.json()

    assert payload["site"] == {
        "id": "site-1",
        "name": "GL36 Demo Campus",
        "timezone": "America/Denver",
    }
    assert payload["summary"]["schedule_count"] == 4
    assert [bucket["category"] for bucket in payload["summary"]["category_buckets"]] == [
        "air_side_occupancy",
        "ventilation_doas",
        "terminal_zone_setback",
        "lighting_ancillary",
    ]
    assert {item["equipment_id"] for item in payload["items"]} == {"eq-ahu-1", "eq-vav-1", "eq-light-1"}
    assert all(item["enabled"] is True for item in payload["items"])


def test_point_command_requires_authentication():
    response = client.post(
        "/api/points/pt-sa-sp/commands",
        json={"value": 54.0, "reason": "test", "confirmed": True},
    )
    assert response.status_code == 401


def test_point_command_rejects_invalid_token():
    response = client.post(
        "/api/points/pt-sa-sp/commands",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"value": 54.0, "reason": "test", "confirmed": True},
    )
    assert response.status_code == 401


def test_point_command_rejects_read_only_user():
    token = _login("readonly", "readonly123")
    response = client.post(
        "/api/points/pt-sa-sp/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={"value": 54.0, "reason": "test", "confirmed": True},
    )
    assert response.status_code == 403

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert events[0]["action_type"] == "point.command"
    assert events[0]["username"] == "readonly"
    assert events[0]["result"] == "failure"
    assert events[0]["reason"] == "read_only_role"


def test_point_release_rejects_read_only_user():
    token = _login("readonly", "readonly123")
    response = client.post(
        "/api/points/pt-sa-sp/release",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test"},
    )
    assert response.status_code == 403

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert events[0]["action_type"] == "point.release"
    assert events[0]["username"] == "readonly"
    assert events[0]["result"] == "failure"
    assert events[0]["reason"] == "read_only_role"


def test_point_command_rejects_missing_reason_and_confirmation():
    token = _login("operator", "operator123")
    missing_reason = client.post(
        "/api/points/pt-sa-sp/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={"value": 54.0, "confirmed": True},
    )
    assert missing_reason.status_code == 400

    missing_confirmation = client.post(
        "/api/points/pt-sa-sp/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={"value": 54.0, "reason": "Commissioning test", "confirmed": False},
    )
    assert missing_confirmation.status_code == 400


def test_point_command_rejects_non_commandable_point():
    token = _login("operator", "operator123")
    response = client.post(
        "/api/points/pt-sat/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={"value": 54.0, "reason": "test", "confirmed": True},
    )
    assert response.status_code == 400


def test_operator_command_updates_point_detail_and_audit():
    token = _login("operator", "operator123")
    response = client.post(
        "/api/points/pt-sa-sp/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={"value": 56.5, "reason": "Commissioning test", "confirmed": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_commanded"] is True
    assert payload["is_overridden"] is True
    assert payload["present_value"] == 56.5
    assert payload["commanded_value"] == 56.5
    assert payload["commanded_by"] == "operator"
    assert payload["original_value"] == 55.0
    assert payload["relinquish_default"] == 55.0

    point_response = client.get("/api/points/pt-sa-sp")
    assert point_response.status_code == 200
    point_payload = point_response.json()
    assert point_payload["present_value"] == 56.5
    assert point_payload["is_commanded"] is True
    assert point_payload["commanded_by"] == "operator"

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert events[0]["action_type"] == "point.command"
    assert events[0]["username"] == "operator"
    assert events[0]["target_id"] == "pt-sa-sp"
    assert events[0]["new_value"] == 56.5
    assert events[0]["reason"] == "Commissioning test"


def test_release_restores_point_detail_and_audit():
    token = _login("operator", "operator123")
    command_response = client.post(
        "/api/points/pt-sa-sp/commands",
        headers={"Authorization": f"Bearer {token}"},
        json={"value": 56.5, "reason": "Commissioning test", "confirmed": True},
    )
    assert command_response.status_code == 200

    release_response = client.post(
        "/api/points/pt-sa-sp/release",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Return to schedule"},
    )
    assert release_response.status_code == 200
    payload = release_response.json()
    assert payload["is_commanded"] is False
    assert payload["is_overridden"] is False
    assert payload["commanded_value"] is None
    assert payload["commanded_by"] is None
    assert payload["present_value"] == 55.0

    point_response = client.get("/api/points/pt-sa-sp")
    assert point_response.status_code == 200
    point_payload = point_response.json()
    assert point_payload["present_value"] == 55.0
    assert point_payload["is_commanded"] is False

    events_response = client.get("/api/audit/events", headers={"Authorization": f"Bearer {token}"})
    assert events_response.status_code == 200
    events = events_response.json()["items"]
    assert events[0]["action_type"] == "point.release"
    assert events[0]["username"] == "operator"
    assert events[0]["target_id"] == "pt-sa-sp"
    assert events[0]["old_value"] == 56.5
    assert events[0]["new_value"] == 55.0
    assert events[0]["reason"] == "Return to schedule"
