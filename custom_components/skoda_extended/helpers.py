"""Small helpers shared by the platforms."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from homeassistant.util import dt as dt_util

_NO_VALUE = {"UNKNOWN", "UNSUPPORTED"}


def get(obj: Any, *path: str) -> Any:
    """Follow attributes, returning None as soon as one is missing."""
    for name in path:
        if obj is None:
            return None
        obj = getattr(obj, name, None)
    return obj


def enum_state(value: Enum | str | None) -> str | None:
    """Lower-case enum value, with UNKNOWN/UNSUPPORTED mapped to None."""
    if value is None:
        return None
    raw = value.value if isinstance(value, Enum) else str(value)
    if raw.upper() in _NO_VALUE:
        return None
    return raw.lower()


def enum_options(enum_cls: type[Enum]) -> list[str]:
    """Options list for an enum sensor."""
    return [m.value.lower() for m in enum_cls if m.value.upper() not in _NO_VALUE]


def timestamp(value: str | None) -> datetime | None:
    """Parse an ISO timestamp from the API."""
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return parsed


def is_on(value: Enum | str | None, *on_values: str) -> bool | None:
    """True/False for a state enum, None when the car doesn't know."""
    if value is None:
        return None
    raw = (value.value if isinstance(value, Enum) else str(value)).upper()
    if raw in _NO_VALUE:
        return None
    return raw in on_values
