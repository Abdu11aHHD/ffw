"""Extraction models and structural PDF validation.

Ported from packages/sukkar_core/lib/src/extraction/{extraction_models,pdf_validation}.dart.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from .metrics import MetricKey, ReportPeriod
from .summary_checks import ConsistencyCheck
from .units import GlucoseUnit


class ExtractionStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"

    @property
    def label_ar(self) -> str:
        return {
            ExtractionStatus.FOUND: "تم العثور عليه",
            ExtractionStatus.NOT_FOUND: "غير موجود في التقرير",
            ExtractionStatus.AMBIGUOUS: "غير واضح",
        }[self]


class FieldValidation(str, Enum):
    VALID = "valid"
    OUT_OF_RANGE = "out_of_range"
    INCONSISTENT = "inconsistent"
    NOT_CROSS_CHECKED = "not_cross_checked"

    @property
    def label_ar(self) -> str:
        return {
            FieldValidation.VALID: "اجتاز التحقق",
            FieldValidation.OUT_OF_RANGE: "خارج النطاق المعقول",
            FieldValidation.INCONSISTENT: "غير متسق مع قيم أخرى",
            FieldValidation.NOT_CROSS_CHECKED: "لم يُتحقق منه آليًا",
        }[self]


class ExtractionMethod(str, Enum):
    LOCAL_TEXT = "local_text"
    AI = "ai"
    LOCAL_AND_AI_AGREE = "local_and_ai_agree"
    LOCAL_AND_AI_DISAGREE = "local_and_ai_disagree"

    @property
    def label_ar(self) -> str:
        return {
            ExtractionMethod.LOCAL_TEXT: "قراءة نص الملف في الخادم",
            ExtractionMethod.AI: "استخراج بالذكاء الاصطناعي فقط",
            ExtractionMethod.LOCAL_AND_AI_AGREE: "تطابق القراءة النصية والذكاء الاصطناعي",
            ExtractionMethod.LOCAL_AND_AI_DISAGREE: "اختلاف بين القراءة النصية والذكاء الاصطناعي",
        }[self]


@dataclass(frozen=True)
class ExtractedField:
    key: MetricKey
    extracted_value: float | None
    unit: str
    extraction_status: ExtractionStatus
    validation: FieldValidation
    method: ExtractionMethod
    source_page: int | None = None
    source_label: str | None = None   # the printed label, never personal data
    source_text: str | None = None    # the printed line the value came from
    messages_ar: list[str] = field(default_factory=list)
    ai_value: float | None = None
    corrected_value: float | None = None
    marked_unavailable: bool = False
    confirmed: bool = False

    @classmethod
    def not_found(cls, key: MetricKey, unit: str) -> "ExtractedField":
        return cls(
            key=key, extracted_value=None, unit=unit,
            extraction_status=ExtractionStatus.NOT_FOUND,
            validation=FieldValidation.NOT_CROSS_CHECKED,
            method=ExtractionMethod.LOCAL_TEXT,
        )

    @property
    def effective_value(self) -> float | None:
        if self.marked_unavailable:
            return None
        return self.corrected_value if self.corrected_value is not None else self.extracted_value

    @property
    def is_corrected(self) -> bool:
        return self.corrected_value is not None and self.corrected_value != self.extracted_value

    @property
    def verification(self) -> str:
        from .metrics import VerificationStatus
        if self.marked_unavailable or self.effective_value is None:
            return VerificationStatus.UNAVAILABLE.value
        return VerificationStatus.VERIFIED.value if self.confirmed else VerificationStatus.NEEDS_REVIEW.value

    @property
    def is_pending(self) -> bool:
        from .metrics import VerificationStatus
        return self.verification == VerificationStatus.NEEDS_REVIEW.value

    @property
    def eligible_for_bulk_confirm(self) -> bool:
        return (
            self.extraction_status is ExtractionStatus.FOUND
            and self.validation is FieldValidation.VALID
            and self.method in (ExtractionMethod.LOCAL_TEXT, ExtractionMethod.LOCAL_AND_AI_AGREE)
        )

    def copy_with(self, **kw) -> "ExtractedField":
        if kw.pop("clear_correction", False):
            kw["corrected_value"] = None
        return replace(self, **kw)

    def to_json(self) -> dict:
        return {
            "key": self.key.value,
            "label_ar": self.key.label_ar,
            "extracted_value": self.extracted_value,
            "corrected_value": self.corrected_value,
            "ai_value": self.ai_value,
            "effective_value": self.effective_value,
            "unit": self.unit,
            "extraction_status": self.extraction_status.value,
            "extraction_status_label_ar": self.extraction_status.label_ar,
            "validation": self.validation.value,
            "validation_label_ar": self.validation.label_ar,
            "method": self.method.value,
            "method_label_ar": self.method.label_ar,
            "source_page": self.source_page,
            "source_label": self.source_label,
            "source_text": self.source_text,
            "messages_ar": list(self.messages_ar),
            "marked_unavailable": self.marked_unavailable,
            "confirmed": self.confirmed,
            "verification": self.verification,
            "eligible_for_bulk_confirm": self.eligible_for_bulk_confirm,
        }


@dataclass(frozen=True)
class ExtractedPeriod:
    status: ExtractionStatus
    period: ReportPeriod | None = None
    source_label: str | None = None
    note_ar: str | None = None
    page: int | None = None

    def to_json(self) -> dict:
        return {
            "status": self.status.value,
            "start": self.period.start.isoformat() if self.period else None,
            "end": self.period.end.isoformat() if self.period else None,
            "days": self.period.days if self.period else None,
            "source_label": self.source_label,
            "note_ar": self.note_ar,
            "page": self.page,
        }


NOT_FOUND_PERIOD = ExtractedPeriod(status=ExtractionStatus.NOT_FOUND)


@dataclass(frozen=True)
class ExtractionResult:
    format_id: str
    format_verified: bool
    glucose_unit: GlucoseUnit
    report_period: ExtractedPeriod
    metrics_period: ExtractedPeriod
    fields: dict[MetricKey, ExtractedField]
    checks: list[ConsistencyCheck]
    warnings_ar: list[str]
    sensor_label: str
    limited_data_notice: bool
    device_label: str | None = None
    report_days_label: int | None = None
    ai_used: bool = False
    page_count: int = 0

    @property
    def found_count(self) -> int:
        return sum(1 for f in self.fields.values() if f.extraction_status is not ExtractionStatus.NOT_FOUND)

    @property
    def has_pending(self) -> bool:
        return any(f.is_pending for f in self.fields.values())

    @property
    def is_empty(self) -> bool:
        return self.found_count == 0

    def copy_with(self, **kw) -> "ExtractionResult":
        return replace(self, **kw)

    def to_json(self) -> dict:
        return {
            "format_id": self.format_id,
            "format_verified": self.format_verified,
            "glucose_unit": self.glucose_unit.value,
            "report_period": self.report_period.to_json(),
            "metrics_period": self.metrics_period.to_json(),
            "fields": [self.fields[k].to_json() for k in MetricKey if k in self.fields],
            "checks": [c.to_json() for c in self.checks],
            "warnings_ar": list(self.warnings_ar),
            "sensor_label": self.sensor_label,
            "limited_data_notice": self.limited_data_notice,
            "device_label": self.device_label,
            "report_days_label": self.report_days_label,
            "ai_used": self.ai_used,
            "found_count": self.found_count,
            "page_count": self.page_count,
        }


def plausible_range(key: MetricKey, unit: GlucoseUnit) -> tuple[float, float]:
    """Sanity bounds used to reject misreads. Not clinical thresholds."""
    if key is MetricKey.MEAN_GLUCOSE:
        return (40, 400) if unit is GlucoseUnit.MGDL else (2.2, 22.2)
    if key is MetricKey.SD:
        return (0, 200) if unit is GlucoseUnit.MGDL else (0, 11.1)
    if key is MetricKey.GMI:
        return (4, 14)
    return (0, 100)


def is_plausible(key: MetricKey, v: float, unit: GlucoseUnit) -> bool:
    lo, hi = plausible_range(key, unit)
    return v == v and abs(v) != float("inf") and lo <= v <= hi


# --------------------------------------------------------- PDF validation

MAX_PDF_BYTES = 15 * 1024 * 1024


class PdfValidationError(str, Enum):
    EMPTY = "empty"
    TOO_LARGE = "too_large"
    UNSUPPORTED_TYPE = "unsupported_type"
    NOT_PDF = "not_pdf"
    TRUNCATED = "truncated"
    ENCRYPTED = "encrypted"
    NO_TEXT = "no_text"
    NO_METRICS = "no_metrics"


@dataclass(frozen=True)
class PdfValidationResult:
    error: PdfValidationError | None
    message_ar: str

    @property
    def is_valid(self) -> bool:
        return self.error is None


OK = PdfValidationResult(None, "الملف صالح للمعالجة.")


def validate_pdf_bytes(file_name: str, data: bytes, max_bytes: int = MAX_PDF_BYTES) -> PdfValidationResult:
    """Structural validation performed before any text extraction.

    It does not prove a PDF is well-formed; the text extractor may still fail,
    which the caller reports as "corrupted or unsupported".
    """
    if not (file_name or "").lower().endswith(".pdf"):
        return PdfValidationResult(PdfValidationError.UNSUPPORTED_TYPE, "نوع الملف غير مدعوم. يُقبل ملف PDF فقط.")
    if not data:
        return PdfValidationResult(PdfValidationError.EMPTY, "الملف فارغ.")
    if len(data) > max_bytes:
        mb = round(max_bytes / (1024 * 1024))
        return PdfValidationResult(PdfValidationError.TOO_LARGE, f"حجم الملف أكبر من الحد المسموح ({mb} ميغابايت).")
    head = data[:1024].decode("latin-1", errors="replace")
    if "%PDF-" not in head:
        return PdfValidationResult(PdfValidationError.NOT_PDF, "الملف لا يبدو ملف PDF صالحًا رغم امتداده.")
    tail = data[-2048:].decode("latin-1", errors="replace")
    if "%%EOF" not in tail:
        return PdfValidationResult(PdfValidationError.TRUNCATED, "يبدو أن الملف ناقص أو تالف (لم يُعثر على نهاية الملف).")
    scan = data[-min(len(data), 4 * 1024 * 1024):].decode("latin-1", errors="replace")
    if "/Encrypt" in scan:
        return PdfValidationResult(PdfValidationError.ENCRYPTED, "الملف محمي أو مشفّر ولا يمكن قراءته.")
    return OK


def format_file_size(n: int) -> str:
    if n < 1024:
        return f"{n} بايت"
    if n < 1024 * 1024:
        return f"{round(n / 1024)} كيلوبايت"
    return f"{n / (1024 * 1024):.1f} ميغابايت"
