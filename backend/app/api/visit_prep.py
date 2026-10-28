"""Appointment-preparation summaries built from verified data only."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db.repository import now_utc
from ..deps import Session, get_session
from ..domain.visit_prep import VisitSummaryBuilder
from ..errors import not_found
from ..services.report_service import cgm_report_from_record

router = APIRouter(prefix="/visit-prep", tags=["visit-prep"])

builder = VisitSummaryBuilder()


def _build(session: Session, report_id: str | None = None) -> dict:
    rows, _ = session.repo.list_reports(session.user_id, limit=50)
    usable = [r for r in rows if r.verified_metrics]
    reports = [cgm_report_from_record(r) for r in usable]

    chosen = None
    if report_id:
        rec = session.repo.get_report(session.user_id, report_id)
        if rec is None or not rec.verified_metrics:
            raise not_found("لم نعثر على تقرير جاهز بهذا المعرّف.")
        chosen = cgm_report_from_record(rec)

    appointments = [a for a in session.repo.list_appointments(session.user_id)
                    if a.scheduled_at >= now_utc()]
    summary = builder.build(
        now=now_utc(), reports=reports,
        followups=session.repo.list_followups(session.user_id),
        appointment=appointments[0].to_json() if appointments else None,
        target_profile=session.target_profile, report=chosen,
    )
    payload = summary.to_json()
    record = next((r for r in usable if r.id == payload.get("report_id")), None)
    ai = record.ai_summary if record else None
    if ai and ai.get("source") == "ai":
        payload["questions_ar"] = list(dict.fromkeys([*payload["questions_ar"], *ai.get("questions_ar", [])]))
        payload["ai_provider"] = ai.get("provider")
        payload["ai_model"] = ai.get("model")
    return payload


@router.get("")
def latest(session: Session = Depends(get_session)) -> dict:
    return _build(session)


@router.get("/{report_id}")
def for_report(report_id: str, session: Session = Depends(get_session)) -> dict:
    return _build(session, report_id)
