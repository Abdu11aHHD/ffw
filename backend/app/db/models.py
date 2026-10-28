"""Row-shaped records shared by the Supabase and in-memory repositories."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..domain.metrics import TargetProfile, UserRole


class ReportStatus:
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    FAILED = "failed"

    LABELS_AR = {
        PROCESSING: "جارٍ تجهيز التقرير",
        NEEDS_REVIEW: "يحتاج مراجعة بعض القيم",
        READY: "التقرير جاهز",
        FAILED: "تعذّرت المعالجة",
    }


class NotificationKind:
    REPORT_READY = "report_ready"
    REPORT_FAILED = "report_failed"
    FOLLOWUP_SUBMITTED = "followup_submitted"
    FOLLOWUP_DECIDED = "followup_decided"
    APPOINTMENT_CREATED = "appointment_created"
    GENERAL = "general"


@dataclass
class ProfileRecord:
    id: str
    pseudo_id: str
    role: UserRole
    target_profile: TargetProfile
    display_name: str | None = None
    health_record_number: str | None = None
    is_synthetic: bool = True

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "pseudo_id": self.pseudo_id,
            "role": self.role.value,
            "target_profile": self.target_profile.value,
            "target_profile_label_ar": self.target_profile.label_ar,
            "display_name": self.display_name,
            "health_record_number": self.health_record_number,
            "is_synthetic": self.is_synthetic,
        }


@dataclass
class ReportRecord:
    id: str
    user_id: str
    status: str
    created_at: datetime
    file_name: str
    file_size_bytes: int
    file_sha256: str | None = None
    page_count: int = 0
    storage_path: str | None = None
    format_id: str | None = None
    format_verified: bool = False
    device_label: str | None = None
    glucose_unit: str = "mg/dL"
    report_period: dict | None = None
    metrics_period: dict | None = None
    data_quality: dict | None = None
    warnings_ar: list[str] = field(default_factory=list)
    extraction: dict | None = None        # ExtractionResult.to_json()
    verified_metrics: list[dict] = field(default_factory=list)
    analysis: dict | None = None          # RuleEvaluation.to_json()
    ai_summary: dict | None = None        # {text, source, fallback_reason_ar}
    error_ar: str | None = None
    provenance: str = "real"

    def summary_json(self) -> dict:
        period = self.metrics_period or self.report_period
        return {
            "id": self.id,
            "status": self.status,
            "status_label_ar": ReportStatus.LABELS_AR.get(self.status, self.status),
            "created_at": self.created_at.isoformat(),
            "file_name": self.file_name,
            "file_size_bytes": self.file_size_bytes,
            "page_count": self.page_count,
            "format_id": self.format_id,
            "format_verified": self.format_verified,
            "device_label": self.device_label,
            "period": period,
            "outcome": (self.analysis or {}).get("outcome"),
            "outcome_title_ar": (self.analysis or {}).get("outcome_title_ar"),
            "data_sufficient": (self.data_quality or {}).get("sufficient"),
            "error_ar": self.error_ar,
            "provenance": self.provenance,
        }

    def detail_json(self) -> dict:
        d = self.summary_json()
        d.update({
            "glucose_unit": self.glucose_unit,
            "report_period": self.report_period,
            "metrics_period": self.metrics_period,
            "data_quality": self.data_quality,
            "warnings_ar": list(self.warnings_ar),
            "extraction": self.extraction,
            "verified_metrics": list(self.verified_metrics),
            "analysis": self.analysis,
            "ai_summary": self.ai_summary,
            "has_stored_file": bool(self.storage_path),
        })
        return d


@dataclass
class AppointmentRecord:
    id: str
    user_id: str
    scheduled_at: datetime
    clinic_label: str
    specialty_ar: str
    is_simulated: bool = True
    status: str = "upcoming"              # upcoming | past | cancelled
    source: str = "prototype"             # prototype | demo_seed
    followup_id: str | None = None
    report_id: str | None = None
    created_at: datetime | None = None
    provenance: str = "synthetic"

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "scheduled_at": self.scheduled_at.isoformat(),
            "clinic_label": self.clinic_label,
            "specialty_ar": self.specialty_ar,
            "is_simulated": self.is_simulated,
            "status": self.status,
            "source": self.source,
            "followup_id": self.followup_id,
            "report_id": self.report_id,
            "provenance": self.provenance,
            "simulated_label_ar": "موعد تجريبي داخل النموذج الأولي — لم يُحجز أي موعد حقيقي",
        }


@dataclass
class NotificationRecord:
    id: str
    user_id: str
    kind: str
    channel: str                           # "personal" | "general"
    title_ar: str
    body_ar: str
    created_at: datetime
    read_at: datetime | None = None
    sender_ar: str = "عضيد"
    dedupe_key: str | None = None
    link: str | None = None

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "channel": self.channel,
            "title_ar": self.title_ar,
            "body_ar": self.body_ar,
            "sender_ar": self.sender_ar,
            "created_at": self.created_at.isoformat(),
            "read": self.read_at is not None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "link": self.link,
        }
