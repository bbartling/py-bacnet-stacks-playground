from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

class CalculationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    algorithm: str
    enabled: bool = True
    inputs: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None

class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1.0"
    project: dict[str, Any] = Field(default_factory=dict)
    assumptions: dict[str, Any] = Field(default_factory=dict)
    calculations: list[CalculationSpec]
