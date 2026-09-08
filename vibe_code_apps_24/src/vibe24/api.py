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
        return {"ok": True, "claim": "SURROGATE_PLANT_V1"}

    @app.get("/status")
    def status() -> dict:
        return rt.status()

    @app.get("/points")
    def points() -> dict:
        return {"points": rt.bus.snapshot()}

    @app.post("/points/{name}/write")
    def write_point(name: str, body: WriteBody) -> dict:
        try:
            present = rt.bus.write(name, body.value, priority=body.priority, source=body.source)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state = rt.bus.get(name)
        return {
            "name": name,
            "present_value": present,
            "winning_priority": state.winning_priority(),
            "winning_source": state.winning_source(),
        }

    @app.post("/points/{name}/relinquish")
    def relinquish_point(name: str, body: RelinquishBody) -> dict:
        try:
            present = rt.bus.relinquish(name, priority=body.priority)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state = rt.bus.get(name)
        return {
            "name": name,
            "present_value": present,
            "winning_priority": state.winning_priority(),
            "winning_source": state.winning_source(),
        }

    @app.post("/tick")
    def manual_tick(sim_minutes: float = 1.0) -> dict:
        sensors = rt.tick(sim_minutes)
        return {"sensors": sensors, "status": rt.status()}

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    return app
