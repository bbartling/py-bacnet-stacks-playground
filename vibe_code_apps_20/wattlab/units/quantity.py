"""Typed, tagged engineering quantities."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Iterable

from .convert import convert


@dataclass(frozen=True, slots=True)
class Quantity:
    """A scalar value carrying its unit, engineering dimension, and tags."""

    value: float
    unit: str
    dimension: str
    tags: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        number = float(self.value)
        if not isfinite(number):
            raise ValueError("Quantity value must be finite")
        if not self.unit.strip():
            raise ValueError("Quantity unit must not be empty")
        if not self.dimension.strip():
            raise ValueError("Quantity dimension must not be empty")
        normalized_tags = frozenset(str(tag).strip() for tag in self.tags if str(tag).strip())
        object.__setattr__(self, "value", number)
        object.__setattr__(self, "tags", normalized_tags)

    @property
    def is_public(self) -> bool:
        """Whether the quantity is approved for public-facing output."""

        return "public" in self.tags

    def to(self, unit: str) -> "Quantity":
        """Return this quantity converted to ``unit``, retaining metadata."""

        return Quantity(convert(self.value, self.unit, unit), unit, self.dimension, self.tags)


def public_quantity(
    value: float,
    unit: str,
    dimension: str,
    *,
    tags: Iterable[str] = (),
) -> Quantity:
    """Create a quantity explicitly tagged for public display."""

    return Quantity(value, unit, dimension, frozenset(tags) | {"public"})
