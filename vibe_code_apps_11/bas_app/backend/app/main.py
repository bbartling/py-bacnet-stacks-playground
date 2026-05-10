"""FastAPI application for the first runnable BAS backend slice."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .alarms import ack_alarm, export_alarm_csv, list_active_alarms, list_alarm_history, shelve_alarm
from .auth import demo_user_payload, get_user_by_token, issue_token, verify_credentials
from .commands import command_point, release_point
from .audit import list_events, record_event
from .sweeps import read_demo_data_sweep
from .services import read_demo_site, read_equipment, read_equipment_points, read_navigation, read_point, read_schedules
from .auth import DemoUser
from .trends import export_trend_samples_csv, list_trend_points, query_trend_samples

app = FastAPI(title="BAS Head-End Demo", version="0.1.0")
bearer_scheme = HTTPBearer(auto_error=False)


class PointCommandRequest(BaseModel):
    value: Any
    reason: str | None = None
    confirmed: bool | None = None


class PointReleaseRequest(BaseModel):
    reason: str | None = None


class AlarmActionRequest(BaseModel):
    reason: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> DemoUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = get_user_by_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


@app.get("/api/demo/site")
def demo_site() -> dict[str, object]:
    return read_demo_site()


@app.get("/api/demo/navigation")
def demo_navigation() -> dict[str, object]:
    return read_navigation()


@app.get("/api/demo/data-sweep")
def demo_data_sweep() -> dict[str, object]:
    return read_demo_data_sweep()


@app.get("/api/equipment/{equipment_id}")
def equipment_detail(equipment_id: str) -> dict[str, object]:
    equipment = read_equipment(equipment_id)
    if equipment is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return equipment


@app.get("/api/equipment/{equipment_id}/points")
def equipment_points(equipment_id: str) -> list[dict[str, object]]:
    points = read_equipment_points(equipment_id)
    if points is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return points


@app.get("/api/points/{point_id}")
def point_detail(point_id: str) -> dict[str, object]:
    point = read_point(point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="Point not found")
    return point


@app.get("/api/schedules")
def schedules(_user: DemoUser = Depends(current_user)) -> dict[str, object]:
    return read_schedules()


@app.get("/api/summary")
def summary(user: DemoUser = Depends(current_user)) -> dict[str, object]:
    navigation = read_navigation()
    return {
        "user": demo_user_payload(user),
        "site": navigation["site"],
        "summary": {
            **navigation["summary"],
            "active_alarm_count": len(list_active_alarms()),
            "recent_audit_event_count": len(list_events()),
        },
    }


@app.post("/api/points/{point_id}/commands")
def point_command(
    point_id: str,
    payload: PointCommandRequest,
    user: DemoUser = Depends(current_user),
) -> dict[str, object]:
    return command_point(user, point_id, payload.value, payload.reason, payload.confirmed)


@app.post("/api/points/{point_id}/release")
def point_release(
    point_id: str,
    payload: PointReleaseRequest,
    user: DemoUser = Depends(current_user),
) -> dict[str, object]:
    return release_point(user, point_id, payload.reason)


@app.post("/api/auth/login")
def auth_login(payload: dict[str, str]) -> dict[str, object]:
    username = payload.get("username", "")
    password = payload.get("password", "")
    user = verify_credentials(username, password)
    if user is None:
        record_event("auth.login", username, "failure", "invalid_credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = issue_token(user.username)
    record_event("auth.login", user.username, "success", "token_issued")
    return {"access_token": token, "token_type": "bearer", "user": demo_user_payload(user)}


@app.get("/api/auth/me")
def auth_me(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict[str, object]:
    user = current_user(credentials)
    return {"user": demo_user_payload(user)}


@app.get("/api/audit/events")
def audit_events(user: DemoUser = Depends(current_user)) -> dict[str, object]:
    return {"items": list_events()}


@app.get("/api/trends/points")
def trends_points() -> dict[str, object]:
    return {"points": list_trend_points()}


@app.get("/api/trends/samples")
def trends_samples(point_ids: str = "", hours: int = 4) -> dict[str, object]:
    return query_trend_samples(point_ids, hours)


@app.get("/api/trends/export.csv")
def trends_export_csv(point_ids: str = "", hours: int = 4) -> Response:
    return export_trend_samples_csv(point_ids, hours)


@app.get("/api/alarms/active")
def alarms_active() -> dict[str, object]:
    return {"items": list_active_alarms()}


@app.get("/api/alarms/history")
def alarms_history() -> dict[str, object]:
    return {"items": list_alarm_history()}


@app.get("/api/alarms/export.csv")
def alarms_export_csv() -> Response:
    return Response(
        content=export_alarm_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bas-alarms.csv"'},
    )


@app.post("/api/alarms/{alarm_id}/ack")
def alarms_ack(
    alarm_id: str,
    payload: AlarmActionRequest,
    user: DemoUser = Depends(current_user),
) -> dict[str, object]:
    return ack_alarm(user, alarm_id, payload.reason)


@app.post("/api/alarms/{alarm_id}/shelve")
def alarms_shelve(
    alarm_id: str,
    payload: AlarmActionRequest,
    user: DemoUser = Depends(current_user),
) -> dict[str, object]:
    return shelve_alarm(user, alarm_id, payload.reason)
