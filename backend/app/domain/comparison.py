"""Comparison between two CGM reporting periods.

Reports are compared ONLY when metrics, units, definitions and reporting
periods are compatible. Incompatible pairs produce a documented refusal
rather than a misleading delta.
Informed by packages/sukkar_core/lib/src/comparison/trends.dart.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .metrics import CgmReport, MetricKey
from .units import GlucoseUnit, ar_period, format_number

COMPARABLE_METRICS = [
    MetricKey.TIME_IN_RANGE,
    MetricKey.TIME_BELOW_RANGE_TOTAL,
    MetricKey.TIME_VERY_LOW,
    MetricKey.TIME_ABOVE_RANGE_TOTAL,
    MetricKey.TIME_VERY_HIGH,
    MetricKey.MEAN_GLUCOSE,
    MetricKey.GMI,
    MetricKey.CV,
]

METHOD_VERSION = "cgm_periods.v1"


@dataclass(frozen=True)
class MetricDelta:
    key: MetricKey
    previous: float
    current: float
    unit: str

    @property
    def delta(self) -> float:
        return self.current - self.previous

    def to_json(self) -> dict:
        sign = "+" if self.delta > 0 else ""
        return {
            "key": self.key.value,
            "label_ar": self.key.label_ar,
            "previous": self.previous,
            "current": self.current,
            "delta": self.delta,
            "unit": self.unit,
            "delta_text_ar": f"{sign}{format_number(self.delta)}{'%' if self.unit == '%' else ' ' + self.unit}",
        }


@dataclass(frozen=True)
class CgmPeriodComparison:
    comparable: bool
    reason_ar: str | None
    previous_period_ar: str | None = None
    current_period_ar: str | None = None
    previous_days: int | None = None
    current_days: int | None = None
    deltas: list[MetricDelta] = field(default_factory=list)
    caveats_ar: list[str] = field(default_factory=list)
    method_version: str = METHOD_VERSION

    def to_json(self) -> dict:
        return {
            "comparable": self.comparable,
            "reason_ar": self.reason_ar,
            "previous_period_ar": self.previous_period_ar,
            "current_period_ar": self.current_period_ar,
            "previous_days": self.previous_days,
            "current_days": self.current_days,
            "deltas": [d.to_json() for d in self.deltas],
            "caveats_ar": list(self.caveats_ar),
            "method_version": self.method_version,
        }


def compare_latest_cgm_periods(reports: list[CgmReport]) -> CgmPeriodComparison:
    dated = [r for r in reports if r.effective_period is not None]
    dated.sort(key=lambda r: r.effective_period.end)
    if len(dated) < 2:
        return CgmPeriodComparison(False, "لا يوجد تقريران بفترات معروفة للمقارنة التاريخية.")

    current, previous = dated[-1], dated[-2]
    cp, pp = current.effective_period, previous.effective_period

    if current.glucose_unit is not previous.glucose_unit:
        return CgmPeriodComparison(
            False, "وحدتا قياس السكر مختلفتان بين التقريرين، فلا تجري المقارنة تلقائيًا.")
    if current.format_id != previous.format_id:
        return CgmPeriodComparison(
            False, "التقريران من تنسيقين مختلفين، وقد تختلف تعريفات المؤشرات بينهما؛ المقارنة التلقائية متوقفة.")
    if cp.overlaps(pp):
        return CgmPeriodComparison(
            False, "فترتا التقريرين متداخلتان، فالمقارنة بينهما غير ذات معنى.")

    caveats: list[str] = []
    if abs(cp.days - pp.days) > max(3, round(0.25 * pp.days)):
        caveats.append(
            f"طول الفترتين مختلف ({pp.days} يومًا مقابل {cp.days} يومًا)؛ قارن بحذر.")
    for r, name in ((previous, "السابق"), (current, "الحالي")):
        if not r.quality.sufficient:
            caveats.append(f"بيانات التقرير {name} لا تستوفي حد الكفاية (14 يومًا و70% تغطية).")

    deltas: list[MetricDelta] = []
    for k in COMPARABLE_METRICS:
        a, b = previous.verified_value(k), current.verified_value(k)
        if a is None or b is None:
            continue
        pm, cm = previous.metric(k), current.metric(k)
        if pm.unit != cm.unit:
            continue
        deltas.append(MetricDelta(k, a, b, cm.unit))

    if not deltas:
        return CgmPeriodComparison(
            False, "لا توجد مؤشرات موثّقة مشتركة بين التقريرين للمقارنة.")

    return CgmPeriodComparison(
        comparable=True, reason_ar=None,
        previous_period_ar=ar_period(pp.start, pp.end),
        current_period_ar=ar_period(cp.start, cp.end),
        previous_days=pp.days, current_days=cp.days,
        deltas=deltas, caveats_ar=caveats,
    )
