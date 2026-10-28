"""Deterministic cross-checks between printed summary metrics.

Ported from packages/sukkar_core/lib/src/cgm/summary_checks.dart.
The AI is never asked to judge numeric consistency.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import gmi as gmi_mod
from .metrics import DataQuality, MetricKey, MetricValue, ReportPeriod, ValueOrigin, VerificationStatus
from .units import format_number


class SummaryTolerances:
    BAND_SUM = 2.0
    TOTAL_VS_BANDS = 1.0
    CV_VS_SD_MEAN = 1.0


@dataclass(frozen=True)
class ConsistencyCheck:
    id: str
    passed: bool | None  # None = could not be evaluated (a value was missing)
    message_ar: str
    involved: set[MetricKey] = field(default_factory=set)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "passed": self.passed,
            "message_ar": self.message_ar,
            "involved": sorted(k.value for k in self.involved),
        }


BANDS = [
    MetricKey.TIME_VERY_LOW,
    MetricKey.TIME_LOW,
    MetricKey.TIME_IN_RANGE,
    MetricKey.TIME_HIGH,
    MetricKey.TIME_VERY_HIGH,
]


def run_summary_checks(v: dict[MetricKey, float | None]) -> list[ConsistencyCheck]:
    """Deterministic checks on a set of summary values (mg/dL basis)."""
    checks: list[ConsistencyCheck] = []

    def g(k: MetricKey) -> float | None:
        return v.get(k)

    if all(g(k) is not None for k in BANDS):
        s = sum(g(k) for k in BANDS)  # type: ignore[misc]
        ok = abs(s - 100) <= SummaryTolerances.BAND_SUM
        checks.append(ConsistencyCheck(
            id="band_sum",
            passed=ok,
            message_ar=(f"مجموع نطاقات السكر الخمسة {format_number(s)}% (متسق)." if ok
                        else f"مجموع نطاقات السكر الخمسة {format_number(s)}% ولا يقارب 100%."),
            involved=set(BANDS),
        ))
    else:
        checks.append(ConsistencyCheck(
            id="band_sum", passed=None,
            message_ar="تعذّر التحقق من مجموع النطاقات لنقص بعض القيم.",
            involved=set(BANDS),
        ))

    def total_check(cid: str, total: MetricKey, a: MetricKey, b: MetricKey, name_ar: str) -> None:
        if g(total) is None or g(a) is None or g(b) is None:
            return
        s = g(a) + g(b)  # type: ignore[operator]
        ok = abs(g(total) - s) <= SummaryTolerances.TOTAL_VS_BANDS  # type: ignore[operator]
        checks.append(ConsistencyCheck(
            id=cid, passed=ok,
            message_ar=(f"{name_ar} {format_number(g(total))}% يطابق مجموع فئتيه ({format_number(s)}%)." if ok
                        else f"{name_ar} {format_number(g(total))}% لا يطابق مجموع فئتيه ({format_number(s)}%)."),
            involved={total, a, b},
        ))

    total_check("tbr_total", MetricKey.TIME_BELOW_RANGE_TOTAL, MetricKey.TIME_VERY_LOW,
                MetricKey.TIME_LOW, "إجمالي الوقت تحت النطاق")
    total_check("tar_total", MetricKey.TIME_ABOVE_RANGE_TOTAL, MetricKey.TIME_HIGH,
                MetricKey.TIME_VERY_HIGH, "إجمالي الوقت فوق النطاق")

    triple = [MetricKey.TIME_BELOW_RANGE_TOTAL, MetricKey.TIME_IN_RANGE, MetricKey.TIME_ABOVE_RANGE_TOTAL]
    if all(g(k) is not None for k in triple):
        s = sum(g(k) for k in triple)  # type: ignore[misc]
        ok = abs(s - 100) <= SummaryTolerances.BAND_SUM
        checks.append(ConsistencyCheck(
            id="triple_sum", passed=ok,
            message_ar=(f"تحت النطاق + ضمنه + فوقه = {format_number(s)}% (متسق)." if ok
                        else f"تحت النطاق + ضمنه + فوقه = {format_number(s)}% ولا يقارب 100%."),
            involved=set(triple),
        ))

    if g(MetricKey.GMI) is not None and g(MetricKey.MEAN_GLUCOSE) is not None:
        expected = gmi_mod.percent_from_mean_mgdl(g(MetricKey.MEAN_GLUCOSE))  # type: ignore[arg-type]
        ok = gmi_mod.is_consistent(g(MetricKey.GMI), g(MetricKey.MEAN_GLUCOSE))  # type: ignore[arg-type]
        checks.append(ConsistencyCheck(
            id="gmi_mean", passed=ok,
            message_ar=(f"قيمة GMI تتسق مع متوسط السكر (المحسوب {format_number(expected, 2)}%)." if ok
                        else f"قيمة GMI المطبوعة لا تتسق مع متوسط السكر (المتوقع {format_number(expected, 2)}%)."),
            involved={MetricKey.GMI, MetricKey.MEAN_GLUCOSE},
        ))

    if (g(MetricKey.CV) is not None and g(MetricKey.SD) is not None
            and g(MetricKey.MEAN_GLUCOSE) is not None and g(MetricKey.MEAN_GLUCOSE) > 0):  # type: ignore[operator]
        expected = g(MetricKey.SD) / g(MetricKey.MEAN_GLUCOSE) * 100  # type: ignore[operator]
        ok = abs(g(MetricKey.CV) - expected) <= SummaryTolerances.CV_VS_SD_MEAN  # type: ignore[operator]
        checks.append(ConsistencyCheck(
            id="cv_sd_mean", passed=ok,
            message_ar=(f"قيمة CV تتسق مع SD ÷ المتوسط ({format_number(expected)}%)." if ok
                        else f"قيمة CV لا تتسق مع SD ÷ المتوسط ({format_number(expected)}%)."),
            involved={MetricKey.CV, MetricKey.SD, MetricKey.MEAN_GLUCOSE},
        ))

    return checks


def with_derived_metrics(metrics: dict[MetricKey, MetricValue]) -> dict[MetricKey, MetricValue]:
    """Adds metrics derivable from verified ones, without overwriting anything."""
    out = dict(metrics)

    def vv(k: MetricKey) -> float | None:
        m = out.get(k)
        return m.value if (m is not None and m.is_verified) else None

    def missing(k: MetricKey) -> bool:
        m = out.get(k)
        return m is None or not m.is_available

    def derive(target: MetricKey, value: float | None, unit: str, note_ar: str) -> None:
        if value is None or not missing(target):
            return
        out[target] = MetricValue(
            key=target, value=value, unit=unit,
            origin=ValueOrigin.CALCULATED_FROM_METRICS,
            status=VerificationStatus.VERIFIED, note=note_ar,
        )

    vl, lo = vv(MetricKey.TIME_VERY_LOW), vv(MetricKey.TIME_LOW)
    derive(MetricKey.TIME_BELOW_RANGE_TOTAL,
           (vl + lo) if (vl is not None and lo is not None) else None,
           "%", "مجموع فئتي أقل من 54 و54–69")
    hi, vh = vv(MetricKey.TIME_HIGH), vv(MetricKey.TIME_VERY_HIGH)
    derive(MetricKey.TIME_ABOVE_RANGE_TOTAL,
           (hi + vh) if (hi is not None and vh is not None) else None,
           "%", "مجموع فئتي 181–250 وأعلى من 250")
    mean = vv(MetricKey.MEAN_GLUCOSE)
    derive(MetricKey.GMI,
           gmi_mod.percent_from_mean_mgdl(mean) if mean is not None else None,
           "%", "محسوب من متوسط السكر بمعادلة GMI")
    return out


def quality_from_summary(
    metrics_period: ReportPeriod | None,
    printed_sensor_percent: float | None,
    sensor_label: str,
    limited_data_notice: bool = False,
) -> DataQuality:
    """Data quality for a printed summary report (no raw readings)."""
    reasons: list[str] = []
    days = metrics_period.days if metrics_period else None

    if days is None:
        reasons.append("لم تُحدَّد فترة البيانات في التقرير.")
    elif days < DataQuality.MIN_DAYS:
        reasons.append(f"مدة البيانات {days} يومًا، والتوصية العامة 14 يومًا على الأقل.")

    if printed_sensor_percent is None:
        reasons.append("لم يُذكر في التقرير ما يكفي لتقييم تغطية بيانات الحساس.")
    elif printed_sensor_percent < DataQuality.MIN_COVERAGE_PERCENT:
        reasons.append(
            f"{sensor_label} {format_number(printed_sensor_percent)}% كما طُبعت، والتوصية العامة 70% على الأقل."
        )

    if limited_data_notice:
        reasons.append("يذكر التقرير أن بعض الأيام بياناتها محدودة أو غير موجودة.")

    sufficient = (
        days is not None
        and days >= DataQuality.MIN_DAYS
        and printed_sensor_percent is not None
        and printed_sensor_percent >= DataQuality.MIN_COVERAGE_PERCENT
    )
    return DataQuality(
        days_of_data=days,
        coverage_percent=printed_sensor_percent,
        coverage_source=f"{sensor_label} كما طُبعت في التقرير (لا يوضح التقرير مقام النسبة)",
        sufficient=sufficient,
        reasons_ar=reasons,
    )
