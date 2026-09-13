"""FastAPI surface for the live twin dashboard."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .runtime import TwinRuntime

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


class WriteBody(BaseModel):
    value: float
    priority: int = Field(default=8, ge=1, le=16)
    source: str = "ui"


class RelinquishBody(BaseModel):
    priority: int = Field(default=8, ge=1, le=16)


class SpeedBody(BaseModel):
    realtime_factor: float = Field(..., ge=1, le=60, description="1..60 (wall sec/sim-min = 60/factor)")


class PauseBody(BaseModel):
    paused: bool


def create_app(runtime: TwinRuntime | None = None, *, auto_tick: bool = True) -> FastAPI:
    rt = runtime or TwinRuntime()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if auto_tick:
            rt.start_background_ticker()
        yield
        rt.stop_background_ticker()

    app = FastAPI(title="Vibe 24 Live Twin", version="0.1.0", lifespan=lifespan)
    app.state.runtime = rt

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "claim": rt.claim}

    @app.get("/status")
    def status() -> dict:
        return rt.status()

    @app.get("/points")
    def points() -> dict:
        rt._publish_effective_setpoints()
        return {
            "points": rt.bus.snapshot(),
            "claim": rt.claim,
            "clock": rt.sim_clock(),
        }

    @app.post("/points/{name}/write")
    def write_point(name: str, body: WriteBody) -> dict:
        try:
            present = rt.bus.write(name, body.value, priority=body.priority, source=body.source)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        rt._publish_effective_setpoints()
        state = rt.bus.get(name)
        return {
            "name": name,
            "present_value": present,
            "winning_priority": state.winning_priority(),
            "winning_source": state.winning_source(),
            "heat_eff": rt.bus.present("HEAT-EFF"),
            "cool_eff": rt.bus.present("COOL-EFF"),
        }

    @app.post("/points/{name}/relinquish")
    def relinquish_point(name: str, body: RelinquishBody) -> dict:
        try:
            present = rt.bus.relinquish(name, priority=body.priority)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        rt._publish_effective_setpoints()
        state = rt.bus.get(name)
        return {
            "name": name,
            "present_value": present,
            "winning_priority": state.winning_priority(),
            "winning_source": state.winning_source(),
            "heat_eff": rt.bus.present("HEAT-EFF"),
            "cool_eff": rt.bus.present("COOL-EFF"),
        }

    @app.post("/tick")
    def manual_tick(sim_minutes: float = 1.0) -> dict:
        sensors = rt.tick(sim_minutes)
        return {"sensors": sensors, "status": rt.status()}

    @app.post("/speed")
    def set_speed(body: SpeedBody) -> dict:
        try:
            clock = rt.set_speed(body.realtime_factor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "clock": clock, "claim": rt.claim}

    @app.post("/pause")
    def set_pause(body: PauseBody) -> dict:
        clock = rt.set_paused(body.paused)
        return {"ok": True, "clock": clock}

    @app.post("/step")
    def step_once(sim_minutes: float = 1.0) -> dict:
        """Advance one (or N) sim-minutes while paused — for inspecting mid-sim SP changes."""
        was = rt.paused
        rt.paused = True
        sensors = rt.tick(sim_minutes)
        rt.paused = was
        return {"sensors": sensors, "clock": rt.sim_clock()}

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    return app
