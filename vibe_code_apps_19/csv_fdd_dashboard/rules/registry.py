"""Discover and run rule plugins from rules/plugins/*.py.

Security model: plugins are Python files shipped in the repo/fork and imported at
startup. The HTTP API only references rules by id and passes validated numeric
params. Nothing in this module executes code supplied over the network.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import ComputeFn, RuleContext, RuleManifest, RuleResult

PLUGIN_DIR = Path(__file__).resolve().parent / "plugins"


@dataclass
class LoadedRule:
    manifest: RuleManifest
    compute: ComputeFn
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {**self.manifest.model_dump(), "source": self.source}


class RuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[str, LoadedRule] = {}
        self._errors: list[dict[str, str]] = []

    @property
    def errors(self) -> list[dict[str, str]]:
        return self._errors

    def discover(self, plugin_dir: Path | None = None) -> "RuleRegistry":
        self._rules.clear()
        self._errors.clear()
        base = plugin_dir or PLUGIN_DIR
        if not base.is_dir():
            return self
        for path in sorted(base.glob("*.py")):
            if path.name.startswith("_"):
                continue
            self._load_file(path)
        return self

    def _load_file(self, path: Path) -> None:
        mod_name = f"rules._loaded_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load spec for {path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            manifest = getattr(module, "RULE", None)
            compute = getattr(module, "compute", None)
            if manifest is None or compute is None:
                raise AttributeError("plugin must define RULE and compute()")
            if not isinstance(manifest, RuleManifest):
                manifest = RuleManifest.model_validate(manifest)
            self._rules[manifest.id] = LoadedRule(manifest=manifest, compute=compute, source=path.name)
        except Exception as exc:  # noqa: BLE001 - surface plugin errors to UI
            self._errors.append({"file": path.name, "error": f"{type(exc).__name__}: {exc}"})

    def ids(self) -> list[str]:
        return list(self._rules.keys())

    def manifests(self) -> list[RuleManifest]:
        return [r.manifest for r in self._rules.values()]

    def catalog(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._rules.values()]

    def get(self, rule_id: str) -> LoadedRule | None:
        return self._rules.get(rule_id)

    def run(self, rule_id: str, ctx: RuleContext) -> RuleResult:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise KeyError(f"Unknown rule {rule_id}")
        ctx.params = rule.manifest.clamp(ctx.params)
        result = rule.compute(ctx)
        if not isinstance(result, RuleResult):
            raise TypeError(f"{rule_id}.compute must return RuleResult")
        return result.finalize(ctx.poll_seconds)


_REGISTRY: RuleRegistry | None = None


def get_registry(*, force: bool = False) -> RuleRegistry:
    global _REGISTRY
    if _REGISTRY is None or force or os.environ.get("RULES_ALWAYS_RELOAD") == "1":
        _REGISTRY = RuleRegistry().discover()
    return _REGISTRY
