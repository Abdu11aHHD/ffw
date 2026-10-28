"""Appointments. Every appointment in this prototype is simulated."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db.repository import now_utc
from ..deps import Session, get_session
from ..domain.metrics import TargetProfile
from ..domain.visit_prep import VisitSummaryBuilder
from ..errors import not_found
from ..services.report_service import cgm_report_from_record

router = APIRouter(prefix="/appointments", tags=["appointments"])

PROTOTYPE_NOTE_AR = (
    "جميع المواعيد هنا مواعيد تجريبية داخل النموذج الأولي. لم يُحجز أي موعد حقيقي "
    "في أي منشأة صحية، ولا يرتبط التطبيق بأي نظام حجز رسمي."
)


@router.get("")
def list_appointments(session: Session = Depends(get_session)) -> dict:
    rows = session.repo.list_appointments(session.user_id)
    now = now_utc()
    upcoming = [a for a in rows if a.scheduled_at >= now and a.status != "cancelled"]
    past = [a for a in rows if a.scheduled_at < now or a.status == "cancelled"]
    followups = {f.id: f for f in session.repo.list_followups(session.user_id)}

    def enrich(a):
        d = a.to_json()
        f = followups.get(a.followup_id) if a.followup_id else None
        d["followup"] = {"pseudo_ref": f.pseudo_ref, "status": f.status.value,
                         "status_label_ar": f.status.label_ar} if f else None
        return d

    return {
        "upcoming": [enrich(a) for a in upcoming],
        "past": [enrich(a) for a in sorted(past, key=lambda x: x.scheduled_at, reverse=True)],
        "prototype_note_ar": PROTOTYPE_NOTE_AR,
    }


@router.get("/{appointment_id}")
def get_appointment(appointment_id: str, session: Session = Depends(get_session)) -> dict:
    a = session.repo.get_appointment(session.user_id, appointment_id)
    if a is None:
        raise not_found("لم نعثر على هذا الموعد.")
    payload = a.to_json()
    payload["prototype_note_ar"] = PROTOTYPE_NOTE_AR

    f = session.repo.get_followup(a.followup_id) if a.followup_id else None
    payload["followup"] = f.to_json() if (f and f.user_id == session.user_id) else None

    rec = session.repo.get_report(session.user_id, a.report_id) if a.report_id else None
    if rec is not None:
        reports, _ = session.repo.list_reports(session.user_id, limit=50)
        summary = VisitSummaryBuilder().build(
            now=now_utc(),
            reports=[cgm_report_from_record(r) for r in reports if r.verified_metrics],
            followups=session.repo.list_followups(session.user_id),
            appointment=a.to_json(), target_profile=session.target_profile,
            report=cgm_report_from_record(rec),
        )
        payload["preparation"] = summary.to_json()
    return payload
