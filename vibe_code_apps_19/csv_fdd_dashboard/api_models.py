"""Pydantic request/response models for the FastAPI dashboard API.

Typed bodies give us automatic validation + OpenAPI docs at /docs, and keep the
custom-rule / ML surface strongly typed so forks can rely on a stable contract.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginBody(BaseModel):
    pin: str = ""


class NotesBody(BaseModel):
    page: str = "index"
    note: str = ""
    analyst_name: str = ""


class ConfigBody(BaseModel):
    params: dict[str, Any] | None = None
    notes: dict[str, Any] | None = None
    analyst_name: str | None = None
    package_title: str | None = None
    site_settings: dict[str, Any] | None = None
    units: str | None = None


class RefreshBody(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    notes: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None
    units: str | None = None


class NoteActionBody(BaseModel):
    page: str = "index"
    action: str = "add"  # add | delete
    text: str = ""
    post_id: str = ""
    analyst_name: str = ""


class RunRuleBody(BaseModel):
    rule_id: str = ""
    equipment_id: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
