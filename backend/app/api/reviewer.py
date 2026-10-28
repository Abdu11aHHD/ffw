"""Reviewer dashboard endpoints.

Every route here requires an authenticated session whose profile role is
`reviewer`. Reviewers see the shared snapshot the patient approved and the
report's extracted values and summary - never the patient's identity.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..db.repository import now_utc, ReviewConflictError
from ..deps import Session, get_reviewer_session
from ..domain.followup import (
    Actor,
    AccessDeniedError,
    FollowUpStatus,
    FollowUpWorkflow,
    InvalidTransitionError,
    ReviewDecision,
)
from ..errors import bad_request, conflict, forbidden, not_found
from ..schemas.api import ReviewerDecisionRequest, ReviewerNoteRequest
from ..services import notifications as notify
from ..services.appointments import create_simulated_appointment

router = APIRouter(prefix="/reviewer", tags=["reviewer"])

workflow = FollowUpWorkflow()

OPEN_STATUSES = [
    FollowUpStatus.AWAITING_REVIEW.value,
    FollowUpStatus.UNDER_REVIEW.value,
    FollowUpStatus.MORE_INFO_REQUESTED.value,
    FollowUpStatus.REVIEWED.value,
]


@router.get("/requests")
def queue(
    status: list[str] | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_reviewer_session),
) -> dict:
    statuses = status or OPEN_STATUSES
    rows, total = session.repo.list_reviewer_queue(statuses, limit, offset)
    return {
        "items": [f.to_json() for f in rows],
        "total": total, "limit": limit, "offset": offset,
        "statuses": statuses,
    }


def _request(session: Session, request_id: str):
    f = session.repo.get_followup(request_id)
    if f is None or f.status is FollowUpStatus.DRAFT:
        raise not_found("لم نعثر على طلب مراجعة بهذا المعرّف.")
    return f, Actor(session.user_id, session.role)


@router.get("/requests/{request_id}")
def detail(request_id: str, session: Session = Depends(get_reviewer_session)) -> dict:
    f, _ = _request(session, request_id)
    payload = f.to_json()
    payload.pop("user_id", None)
    if f.report_id and f.snapshot.items:
        rec = session.repo.get_report_any(f.report_id)
        if rec is not None:
            payload["report"] = {
                "id": rec.id,
                "format_id": rec.format_id,
                "format_verified": rec.format_verified,
                "device_label": rec.device_label,
                "glucose_unit": rec.glucose_unit,
                "report_period": rec.report_period,
                "metrics_period": rec.metrics_period,
                "data_quality": rec.data_quality,
                "warnings_ar": rec.warnings_ar,
                "verified_metrics": rec.verified_metrics,
                "extraction": rec.extraction,
                "analysis": rec.analysis,
                "ai_summary": rec.ai_summary,
            }
    appointment = session.repo.appointment_for_followup(f.id)
    payload["appointment"] = appointment.to_json() if appointment else None
    return payload


@router.post("/requests/{request_id}/start")
def start_review(request_id: str, session: Session = Depends(get_reviewer_session)) -> dict:
    f, actor = _request(session, request_id)
    try:
        f = workflow.start_review(f, actor, now_utc())
    except AccessDeniedError as exc:
        raise forbidden(exc.message_ar) from None
    except InvalidTransitionError as exc:
        raise bad_request("invalid_transition", exc.message_ar) from None
    session.repo.save_followup(f)
    return f.to_json()


@router.post("/requests/{request_id}/decide")
def decide(request_id: str, body: ReviewerDecisionRequest,
           session: Session = Depends(get_reviewer_session)) -> dict:
    f, actor = _request(session, request_id)
    expected_at = f.updated_at
    try:
        f = workflow.decide(f, actor, now_utc(), body.decision, body.note_ar)
    except AccessDeniedError as exc:
        raise forbidden(exc.message_ar) from None
    except InvalidTransitionError as exc:
        raise bad_request("invalid_transition", exc.message_ar) from None

    appointment = None
    if body.decision.creates_simulated_appointment:
        appointment = create_simulated_appointment(session.repo, f, persist=False)
        f.appointment_id = appointment.id

    class NotificationBuffer:
        def __init__(self): self.items = []
        def create_notification(self, n): self.items.append(n); return n
    buffer = NotificationBuffer()
    notify.followup_decided(buffer, f, body.decision)
    if appointment is not None:
        notify.appointment_created(buffer, f.user_id, appointment.id,
                                   appointment.clinic_label, appointment.scheduled_at)
    try:
        session.repo.commit_review(f, expected_at, appointment, buffer.items)
    except ReviewConflictError:
        raise conflict("review_changed", "تغيّر الطلب أثناء المراجعة. حدّث الصفحة قبل المحاولة مرة أخرى.") from None

    payload = f.to_json()
    payload["appointment"] = appointment.to_json() if appointment else None
    return payload


@router.post("/requests/{request_id}/notes")
def add_note(request_id: str, body: ReviewerNoteRequest,
             session: Session = Depends(get_reviewer_session)) -> dict:
    f, actor = _request(session, request_id)
    try:
        f = workflow.add_note(f, actor, now_utc(), body.note_ar)
    except AccessDeniedError as exc:
        raise forbidden(exc.message_ar) from None
    except InvalidTransitionError as exc:
        raise bad_request("invalid_transition", exc.message_ar) from None
    session.repo.save_followup(f)
    return f.to_json()
