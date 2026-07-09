"""SPARQL/model-driven page catalog for Open FDD Vibe Coder dashboard."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any


def _slug(equipment_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", equipment_id).strip("_").lower()


def ahu_page_id(equipment_id: str) -> str:
    return f"ahu_{_slug(equipment_id)}"


@dataclass
class PageSpec:
    id: str
    title: str
    href: str
    kind: str
    available: bool = True
    equipment_ids: list[str] = field(default_factory=list)
    nav_group: str | None = None
    sort_order: int = 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "href": self.href,
            "kind": self.kind,
            "available": self.available,
            "equipment_ids": self.equipment_ids,
            "nav_group": self.nav_group,
        }


_REGISTRY_CACHE: list[PageSpec] | None = None


def discover_pages(*, force: bool = False) -> list[PageSpec]:
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None and not force:
        return _REGISTRY_CACHE

    pages: list[PageSpec] = [
        PageSpec("index", "Overview", "index.html", "overview", sort_order=0),
        PageSpec("zones", "Comfort / Zones", "zones.html", "zones", sort_order=10),
        PageSpec("weather", "Weather Sensors", "weather.html", "weather", sort_order=20),
    ]

    ahus: list[str] = []
    chillers: list[str] = []
    boilers: list[str] = []
    try:
        from haystack_rdf.resolver import get_resolver

        resolver = get_resolver()
        resolver.ensure_model()
        ahus = sorted(resolver.list_ahus())
        chillers = sorted(e["id"] for e in resolver.list_equipment(haystack_tag="chiller"))
        boilers = sorted(
            e["id"]
            for e in resolver.list_equipment()
            if e["id"].upper().startswith("BOILER") or "BOILER" in e["id"].upper()
        )
    except Exception:
        ahus = ["AHU_1", "AHU_2"]
        chillers = ["CHILLER_1", "CHILLER_2"]
        boilers = ["BOILERS_PUMPS"]

    for i, eq_id in enumerate(ahus):
        pid = ahu_page_id(eq_id)
        pages.append(PageSpec(
            pid,
            eq_id.replace("_", " "),
            f"{pid}.html",
            "ahu",
            equipment_ids=[eq_id],
            nav_group="airside",
            sort_order=30 + i,
        ))
        if i == 0:
            pages.append(PageSpec("ahu_1", "AHU 1", "ahu_1.html", "ahu", available=True, equipment_ids=[eq_id], nav_group="airside", sort_order=31))
        if i == 1:
            pages.append(PageSpec("ahu_2", "AHU 2", "ahu_2.html", "ahu", available=True, equipment_ids=[eq_id], nav_group="airside", sort_order=32))

    pages.extend([
        PageSpec("economizer", "Economizer / Free Cooling", "economizer.html", "economizer", sort_order=50),
        PageSpec(
            "chiller_plant",
            "Chiller Plant",
            "chiller_plant.html",
            "chiller_plant",
            available=bool(chillers),
            equipment_ids=chillers,
            sort_order=60,
        ),
        PageSpec(
            "boiler_plant",
            "Boiler Plant",
            "boiler_plant.html",
            "boiler_plant",
            available=bool(boilers),
            equipment_ids=boilers,
            sort_order=70,
        ),
        PageSpec("motor_runtime", "Motor Runtime", "motor_runtime.html", "motor_runtime", sort_order=80),
        PageSpec("custom_rules", "Custom / ML Rules", "custom_rules.html", "custom_rules", sort_order=82),
        PageSpec("central_plant", "Central Plant (legacy)", "central_plant.html", "central_plant", available=bool(chillers or boilers), sort_order=85),
        PageSpec("excess_runtime", "Excess Fan (legacy)", "excess_runtime.html", "excess_runtime", sort_order=86),
    ])

    _REGISTRY_CACHE = sorted(pages, key=lambda p: p.sort_order)
    return _REGISTRY_CACHE


def page_ids(*, force: bool = False) -> list[str]:
    return [p.id for p in discover_pages(force=force)]


def page_titles(*, force: bool = False) -> dict[str, str]:
    return {p.id: p.title for p in discover_pages(force=force)}


def is_valid_page(page_id: str) -> bool:
    return page_id in page_titles()


def get_page(page_id: str) -> PageSpec | None:
    for p in discover_pages():
        if p.id == page_id:
            return p
    return None


def resolve_ahu_equipment(page_id: str) -> str | None:
    spec = get_page(page_id)
    if spec and spec.kind == "ahu" and spec.equipment_ids:
        return spec.equipment_ids[0]
    if page_id == "ahu_1":
        return "AHU_1"
    if page_id == "ahu_2":
        return "AHU_2"
    if page_id.startswith("ahu_"):
        slug = page_id[4:]
        for p in discover_pages():
            if p.kind == "ahu" and _slug(p.equipment_ids[0] if p.equipment_ids else "") == slug:
                return p.equipment_ids[0]
    return None


def nav_tree(*, interactive: bool = False) -> list[dict[str, Any]]:
    pages = discover_pages()
    top: list[dict[str, Any]] = []
    airside: list[dict[str, Any]] = []
    seen_ahu: set[str] = set()
    for p in pages:
        if p.nav_group == "airside" and p.kind == "ahu":
            if p.id in ("ahu_1", "ahu_2"):
                continue
            eq = p.equipment_ids[0] if p.equipment_ids else p.id
            if eq in seen_ahu:
                continue
            seen_ahu.add(eq)
            airside.append(p.to_dict())
            continue
        if p.id in ("central_plant", "excess_runtime", "economizer_diagnostics"):
            continue
        top.append(p.to_dict())
    if airside:
        top.insert(3, {"id": "airside", "title": "Air-side Systems", "kind": "group", "children": airside, "available": True})
    if interactive:
        top.append({"id": "data_model", "title": "Data Model", "href": "data_model.html", "kind": "tool", "available": True})
    return top


def clear_registry_cache() -> None:
    global _REGISTRY_CACHE
    _REGISTRY_CACHE = None
