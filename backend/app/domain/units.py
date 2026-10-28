"""Glucose units, deterministic conversions and Arabic formatting.

Ported from packages/sukkar_core/lib/src/common/units.dart.
Conversion factor: 1 mmol/L glucose = 18.0182 mg/dL (molar mass 180.16 / 10).
See docs/METRICS.md.
"""

from __future__ import annotations

import math
from datetime import date
from enum import Enum

MGDL_PER_MMOLL = 18.0182


class GlucoseUnit(str, Enum):
    MGDL = "mg/dL"
    MMOLL = "mmol/L"

    @property
    def label(self) -> str:
        return self.value


def parse_glucose_unit(raw: str) -> GlucoseUnit | None:
    s = (raw or "").lower().replace(" ", "")
    if "mg/dl" in s:
        return GlucoseUnit.MGDL
    if "mmol/l" in s:
        return GlucoseUnit.MMOLL
    return None


def to_mgdl(value: float, unit: GlucoseUnit) -> float:
    return value if unit is GlucoseUnit.MGDL else value * MGDL_PER_MMOLL


def to_mmoll(value: float, unit: GlucoseUnit) -> float:
    return value if unit is GlucoseUnit.MMOLL else value / MGDL_PER_MMOLL


def round_to(value: float, decimals: int = 1) -> float:
    """Round half away from zero (display helper; calculations keep precision)."""
    f = 10.0 ** decimals
    scaled = value * f
    r = math.floor(scaled + 0.5) if scaled >= 0 else math.ceil(scaled - 0.5)
    return r / f


def format_number(value: float, decimals: int = 1) -> str:
    """Format with up to `decimals` decimals and no trailing zeros."""
    r = round_to(value, decimals)
    if r == int(r):
        return str(int(r))
    s = f"{r:.{decimals}f}"
    while "." in s and s.endswith("0"):
        s = s[:-1]
    return s


def days_between(a: date, b: date) -> int:
    return (b - a).days


AR_MONTHS = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]


def ar_date(d: date) -> str:
    """Human-facing Arabic date, e.g. "13 سبتمبر 2026".

    Used instead of ISO dates in any text shown to people, because ISO dates
    are reordered by the bidirectional algorithm inside Arabic sentences.
    """
    return f"{d.day} {AR_MONTHS[d.month - 1]} {d.year}"


def ar_period(start: date, end: date) -> str:
    if start.year == end.year:
        return f"{start.day} {AR_MONTHS[start.month - 1]} إلى {ar_date(end)}"
    return f"{ar_date(start)} إلى {ar_date(end)}"


def iso_date(d: date) -> str:
    return d.isoformat()
