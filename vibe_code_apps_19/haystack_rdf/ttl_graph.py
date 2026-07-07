"""Load synced Haystack TTL and run SPARQL via rdflib."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rdflib import Graph

    from .ttl_service import TtlService

_log = logging.getLogger(__name__)


class TtlGraphError(RuntimeError):
    """Haystack graph missing, invalid, or SPARQL failed."""


class RdfLibRequired(TtlGraphError):
    """rdflib not installed."""


def require_rdflib():
    try:
        import rdflib  # noqa: F401

        return rdflib
    except ImportError as exc:
        raise RdfLibRequired(
            "rdflib is required for Haystack model queries; pip install rdflib"
        ) from exc


def ensure_ttl_on_disk(ttl: TtlService) -> Path:
    if not ttl.ttl_path.is_file():
        _log.info("data_model.ttl missing — syncing from model.json")
        return ttl.sync()
    return ttl.ttl_path


def load_graph(ttl: TtlService | None = None) -> Graph:
    from rdflib import Graph

    from .ttl_service import TtlService

    require_rdflib()
    svc = ttl or TtlService()
    path = ensure_ttl_on_disk(svc)
    graph = Graph()
    try:
        graph.parse(str(path), format="turtle")
    except Exception as exc:
        raise TtlGraphError(f"Invalid Turtle at {path}: {exc}") from exc
    if len(graph) == 0:
        raise TtlGraphError(
            f"TTL graph is empty at {path}; POST /api/rdf/sync-ttl after editing the model"
        )
    return graph


def run_sparql(graph: Graph, query: str) -> list[dict[str, str]]:
    from rdflib.query import ResultRow

    out: list[dict[str, str]] = []
    try:
        for row in graph.query(query):
            if not isinstance(row, ResultRow):
                continue
            item: dict[str, str] = {}
            for key in row.labels:
                val = row[key]
                item[str(key)] = str(val) if val is not None else ""
            out.append(item)
    except Exception as exc:
        raise TtlGraphError(f"SPARQL query failed: {exc}") from exc
    return out


def local_name(term: str, prefix: str) -> str:
    text = str(term or "").strip()
    if not text:
        return ""
    fragment = text
    if "#" in text:
        fragment = text.rsplit("#", 1)[-1]
    elif text.startswith(":"):
        fragment = text[1:]
    lead = f"{prefix}_"
    if fragment.startswith(lead):
        return fragment[len(lead) :]
    return fragment
