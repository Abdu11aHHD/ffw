"""CGM metric keys, values and provenance.

Ported from packages/sukkar_core/lib/src/models/{cgm,enums}.dart.
Range bands follow the 2019 International Consensus on Time in Range,
Table 2 (see docs/SOURCE_MAPPING.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from .units import GlucoseUnit, days_between, iso_date


class MetricKey(str, Enum):
    MEAN_GLUCOSE = "mean_glucose"
    GMI = "gmi"
    CV = "cv"
    SD = "sd"
    TIME_VERY_LOW = "time_very_low"          # < 54 mg/dL  (TBR level 2)
    TIME_LOW = "time_low"                    # 54-69       (TBR level 1)
    TIME_IN_RANGE = "time_in_range"          # 70-180
    TIME_HIGH = "time_high"                  # 181-250     (TAR level 1)
    TIME_VERY_HIGH = "time_very_high"        # > 250       (TAR level 2)
    TIME_BELOW_RANGE_TOTAL = "time_below_range_total"
    TIME_ABOVE_RANGE_TOTAL = "time_above_range_total"
    SENSOR_ACTIVE = "sensor_active"

    @property
    def is_percent(self) -> bool:
        return self in PERCENT_METRICS

    @property
    def label_ar(self) -> str:
        return METRIC_LABELS_AR[self]

    @property
    def short_label_ar(self) -> str:
        return METRIC_SHORT_LABELS_AR[self]


PERCENT_METRICS = {
    MetricKey.CV,
    MetricKey.TIME_VERY_LOW,
    MetricKey.TIME_LOW,
    MetricKey.TIME_IN_RANGE,
    MetricKey.TIME_HIGH,
    MetricKey.TIME_VERY_HIGH,
    MetricKey.TIME_BELOW_RANGE_TOTAL,
    MetricKey.TIME_ABOVE_RANGE_TOTAL,
    MetricKey.SENSOR_ACTIVE,
}

METRIC_LABELS_AR = {
    MetricKey.MEAN_GLUCOSE: "متوسط السكر",
    MetricKey.GMI: "مؤشر إدارة الجلوكوز (GMI)",
    MetricKey.CV: "تذبذب السكر (CV)",
    MetricKey.SD: "الانحراف المعياري (SD)",
    MetricKey.TIME_VERY_LOW: "منخفض جدًا (أقل من 54)",
    MetricKey.TIME_LOW: "منخفض (54–69)",
    MetricKey.TIME_IN_RANGE: "الوقت ضمن النطاق (70–180)",
    MetricKey.TIME_HIGH: "مرتفع (181–250)",
    MetricKey.TIME_VERY_HIGH: "مرتفع جدًا (أعلى من 250)",
    MetricKey.TIME_BELOW_RANGE_TOTAL: "إجمالي الوقت تحت النطاق (أقل من 70)",
    MetricKey.TIME_ABOVE_RANGE_TOTAL: "إجمالي الوقت فوق النطاق (أعلى من 180)",
    MetricKey.SENSOR_ACTIVE: "نسبة عمل الحساس",
}

METRIC_SHORT_LABELS_AR = {
    MetricKey.MEAN_GLUCOSE: "المتوسط",
    MetricKey.GMI: "GMI",
    MetricKey.CV: "CV",
    MetricKey.SD: "SD",
    MetricKey.TIME_VERY_LOW: "<54",
    MetricKey.TIME_LOW: "54–69",
    MetricKey.TIME_IN_RANGE: "TIR",
    MetricKey.TIME_HIGH: "181–250",
    MetricKey.TIME_VERY_HIGH: ">250",
    MetricKey.TIME_BELOW_RANGE_TOTAL: "TBR",
    MetricKey.TIME_ABOVE_RANGE_TOTAL: "TAR",
    MetricKey.SENSOR_ACTIVE: "الحساس",
}


def metric_key_from_wire(s: str) -> MetricKey | None:
    try:
        return MetricKey(s)
    except ValueError:
        return None


# --------------------------------------------------------------- provenance


class DataProvenance(str, Enum):
    REAL = "real"
    SYNTHETIC = "synthetic"

    @property
    def label_ar(self) -> str:
        return "بيانات تجريبية" if self is DataProvenance.SYNTHETIC else "بيانات المستخدم"


class ValueOrigin(str, Enum):
    EXTRACTED_FROM_REPORT = "extracted_from_report"
    CALCULATED_FROM_READINGS = "calculated_from_readings"
    CALCULATED_FROM_METRICS = "calculated_from_metrics"
    USER_CORRECTED = "user_corrected"
    USER_ENTERED = "user_entered"

    @property
    def label_ar(self) -> str:
        return {
            ValueOrigin.EXTRACTED_FROM_REPORT: "مستخرج من التقرير",
            ValueOrigin.CALCULATED_FROM_READINGS: "محسوب من القراءات",
            ValueOrigin.CALCULATED_FROM_METRICS: "محسوب من مؤشرات موثّقة",
            ValueOrigin.USER_CORRECTED: "مصحّح يدويًا",
            ValueOrigin.USER_ENTERED: "مُدخل يدويًا",
        }[self]


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"

    @property
    def label_ar(self) -> str:
        return {
            VerificationStatus.VERIFIED: "موثّق",
            VerificationStatus.NEEDS_REVIEW: "يحتاج تحقق",
            VerificationStatus.UNAVAILABLE: "غير متاح",
            VerificationStatus.REJECTED: "مرفوض",
        }[self]


class UserRole(str, Enum):
    PATIENT = "patient"
    REVIEWER = "reviewer"


class TargetProfile(str, Enum):
    GENERAL_ADULT_T1_T2 = "general_adult_t1_t2"
    OLDER_OR_HIGH_RISK = "older_or_high_risk"
    PREGNANCY = "pregnancy"
    PEDIATRIC = "pediatric"
    UNSPECIFIED = "unspecified"

    @property
    def label_ar(self) -> str:
        return {
            TargetProfile.GENERAL_ADULT_T1_T2: "بالغ مصاب بالسكري من النوع الأول أو الثاني (أهداف عامة)",
            TargetProfile.OLDER_OR_HIGH_RISK: "كبار السن أو الفئات الأعلى خطورة",
            TargetProfile.PREGNANCY: "حمل",
            TargetProfile.PEDIATRIC: "أطفال ويافعون",
            TargetProfile.UNSPECIFIED: "لم يُحدَّد",
        }[self]


class ReportSourceType(str, Enum):
    PDF_UPLOAD = "pdf_upload"
    DEMO_FIXTURE = "demo_fixture"
    READINGS_IMPORT = "readings_import"

    @property
    def label_ar(self) -> str:
        return {
            ReportSourceType.PDF_UPLOAD: "تقرير PDF مرفوع",
            ReportSourceType.DEMO_FIXTURE: "ملف تجريبي",
            ReportSourceType.READINGS_IMPORT: "قراءات مستوردة",
        }[self]


# ------------------------------------------------------------------ values


@dataclass(frozen=True)
class MetricValue:
    """A single metric value with full provenance."""

    key: MetricKey
    value: float | None  # None means unavailable; never replaced with zero.
    unit: str            # '%', 'mg/dL' or 'mmol/L'
    origin: ValueOrigin
    status: VerificationStatus
    source_label: str | None = None
    source_page: int | None = None
    original_extracted_value: float | None = None
    note: str | None = None

    @property
    def is_available(self) -> bool:
        return self.value is not None and self.status not in (
            VerificationStatus.UNAVAILABLE,
            VerificationStatus.REJECTED,
        )

    @property
    def is_verified(self) -> bool:
        return self.is_available and self.status is VerificationStatus.VERIFIED

    def to_json(self) -> dict:
        return {
            "key": self.key.value,
            "label_ar": self.key.label_ar,
            "value": self.value,
            "unit": self.unit,
            "origin": self.origin.value,
            "origin_label_ar": self.origin.label_ar,
            "status": self.status.value,
            "status_label_ar": self.status.label_ar,
            "source_label": self.source_label,
            "source_page": self.source_page,
            "original_extracted_value": self.original_extracted_value,
            "note": self.note,
        }


@dataclass(frozen=True)
class ReportPeriod:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("Period end precedes start")

    @property
    def days(self) -> int:
        """Inclusive calendar days."""
        return days_between(self.start, self.end) + 1

    def contains(self, d: date) -> bool:
        return self.start <= d <= self.end

    def overlaps(self, other: "ReportPeriod") -> bool:
        return not (other.end < self.start or other.start > self.end)

    def __str__(self) -> str:
        return f"{iso_date(self.start)}..{iso_date(self.end)}"


@dataclass(frozen=True)
class DataQuality:
    """Data sufficiency assessment.

    Thresholds (14 days, 70 %) come from the consensus Table 2 recommendations.
    """

    MIN_DAYS = 14
    MIN_COVERAGE_PERCENT = 70.0

    days_of_data: int | None
    coverage_percent: float | None
    coverage_source: str
    sufficient: bool
    reasons_ar: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "days_of_data": self.days_of_data,
            "coverage_percent": self.coverage_percent,
            "coverage_source": self.coverage_source,
            "sufficient": self.sufficient,
            "reasons_ar": list(self.reasons_ar),
        }


@dataclass(frozen=True)
class CgmReport:
    """An accepted CGM report (after extracted values were reviewed)."""

    id: str
    user_id: str
    provenance: DataProvenance
    source_type: ReportSourceType
    glucose_unit: GlucoseUnit
    metrics: dict[MetricKey, MetricValue]
    quality: DataQuality
    created_at: object
    report_period: ReportPeriod | None = None
    metrics_period: ReportPeriod | None = None
    format_id: str | None = None
    device_label: str | None = None
    warnings_ar: list[str] = field(default_factory=list)

    @property
    def effective_period(self) -> ReportPeriod | None:
        return self.metrics_period or self.report_period

    @property
    def has_raw_readings(self) -> bool:
        """Uploaded PDFs carry printed summaries only; no series is invented."""
        return False

    def metric(self, key: MetricKey) -> MetricValue | None:
        return self.metrics.get(key)

    def verified_value(self, key: MetricKey) -> float | None:
        m = self.metrics.get(key)
        return m.value if (m is not None and m.is_verified) else None
