"""Glucose Management Indicator.

Source: Bergenstal RM et al. "Glucose Management Indicator (GMI): a new term
for estimating A1C from continuous glucose monitoring." Diabetes Care
2018;41:2275-2280. See docs/SOURCE_MAPPING.md.
"""

from __future__ import annotations

CONSISTENCY_TOLERANCE_PERCENT = 0.15


def percent_from_mean_mgdl(mean_mgdl: float) -> float:
    """GMI (%) = 3.31 + 0.02392 x mean glucose (mg/dL)."""
    return 3.31 + 0.02392 * mean_mgdl


def mmol_mol_from_mean_mmoll(mean_mmoll: float) -> float:
    """GMI (mmol/mol) = 12.71 + 4.70587 x mean glucose (mmol/L)."""
    return 12.71 + 4.70587 * mean_mmoll


def is_consistent(reported_gmi_percent: float, mean_mgdl: float) -> bool:
    return abs(reported_gmi_percent - percent_from_mean_mgdl(mean_mgdl)) <= CONSISTENCY_TOLERANCE_PERCENT
