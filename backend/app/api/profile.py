"""Authenticated profile and health profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db.models import ReportStatus
from ..deps import Session, get_session
from ..domain.metrics import DataQuality, MetricKey
from ..domain.targets import consensus_targets_for
from ..schemas.api import TargetProfileUpdate

router = APIRouter(tags=["profile"])


@router.get("/me")
def me(session: Session = Depends(get_session)) -> dict:
    return {
        "profile": session.profile.to_json(),
        "demo_mode": session.is_demo,
        "role": session.role.value,
    }


@router.patch("/me/target-profile")
def update_target_profile(body: TargetProfileUpdate, session: Session = Depends(get_session)) -> dict:
    profile = session.repo.set_target_profile(session.user_id, body.target_profile)
    return {"profile": profile.to_json()}


@router.get("/me/health-profile")
def health_profile(session: Session = Depends(get_session)) -> dict:
    """What the ملفي screen shows: identity, the services available to this
    user, and the real state of the Sukkar Plus service."""
    reports, total = session.repo.list_reports(session.user_id, limit=1)
    followups = session.repo.list_followups(session.user_id)
    appointments = session.repo.list_appointments(session.user_id)
    targets = consensus_targets_for(session.target_profile)
    latest = reports[0] if reports else None

    open_followups = [f for f in followups if f.status.is_open]
    return {
        "profile": session.profile.to_json(),
        "targets": {
            "profile": session.target_profile.value,
            "profile_label_ar": session.target_profile.label_ar,
            "notes_ar": targets.notes_ar,
            "items": [
                {"metric": k.value, "label_ar": k.label_ar, "text_ar": s.text_ar, "source_ref": s.source_ref}
                for k, s in targets.targets.items()
            ],
        },
        "sukkar_plus": {
            "reports_count": total,
            "latest_report": latest.summary_json() if latest else None,
            "open_followups": len(open_followups),
            "appointments": len(appointments),
            "data_sufficiency_rule_ar":
                f"تُعدّ البيانات كافية عند {DataQuality.MIN_DAYS} يومًا على الأقل "
                f"وتغطية حساس لا تقل عن {int(DataQuality.MIN_COVERAGE_PERCENT)}%.",
        },
        "metric_catalogue": [
            {"key": k.value, "label_ar": k.label_ar, "short_label_ar": k.short_label_ar,
             "is_percent": k.is_percent}
            for k in MetricKey
        ],
        "report_statuses_ar": ReportStatus.LABELS_AR,
    }
