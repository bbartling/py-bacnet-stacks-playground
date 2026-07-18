from __future__ import annotations
from collections.abc import Callable
from typing import Any

Calculator = Callable[[dict[str, Any]], dict[str, Any]]
_REGISTRY: dict[str, Calculator] = {}

def register(name: str):
    def decorator(func: Calculator) -> Calculator:
        if name in _REGISTRY:
            raise KeyError(f"Calculator already registered: {name}")
        _REGISTRY[name] = func
        return func
    return decorator

def get(name: str) -> Calculator:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown algorithm '{name}'. Available: {sorted(_REGISTRY)}") from exc

def names() -> list[str]:
    return sorted(_REGISTRY)
