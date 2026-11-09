"""
superviseme/utils/timestamps.py
---------------------------------
Timestamp utilities for gradual migration from Unix-int timestamps to
proper Python datetime objects.

Background
----------
The original models store timestamps as db.Integer (Unix epoch seconds).
This module provides:

  - ``utcnow()``  — current UTC datetime (use in new code instead of
    int(time.time()))
  - ``to_dt(value)``  — coerce Integer or datetime to datetime; safe to call
    on either type, so read-side code stays clean during the migration.
  - ``to_int(value)``  — coerce datetime or int to int; safe for write-side
    code that still talks to Integer columns.
  - ``age_days(value)``  — number of days since the given timestamp.

Migration path
--------------
1. New routes: use ``utcnow()`` and ``db.DateTime`` columns.
2. Existing routes: replace ``int(time.time())`` with ``to_int(utcnow())``
   (no behaviour change, easier to find later).
3. Per-model migration: when a model's Integer timestamp is converted to
   DateTime, replace ``to_int(...)`` writes with plain ``utcnow()`` and
   ``to_dt(...)`` reads with plain column access.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def to_dt(value: int | float | datetime | None) -> datetime | None:
    """Coerce *value* to a UTC-aware datetime.

    - ``None``  → ``None``
    - ``int`` / ``float``  → interpreted as Unix epoch seconds (UTC).
    - ``datetime``  → returned as-is (naive datetimes assumed UTC).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    raise TypeError(f"Cannot convert {type(value).__name__} to datetime")


def to_int(value: datetime | int | float | None) -> int | None:
    """Coerce *value* to a Unix timestamp integer.

    - ``None``  → ``None``
    - ``datetime``  → ``.timestamp()`` rounded to int.
    - ``int`` / ``float``  → cast to int.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return int(value.timestamp())
    return int(value)


def age_days(value: int | float | datetime | None) -> int | None:
    """Return the number of whole days since *value*, or ``None``."""
    dt = to_dt(value)
    if dt is None:
        return None
    delta = utcnow() - dt
    return max(0, delta.days)
