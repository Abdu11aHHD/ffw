"""Patient-side follow-up requests."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db.repository import new_id, new_pseudo, now_utc
from ..deps import Session, get_session
from ..domain.followup import (
    Actor,
    AccessDeniedError,
    DuplicateRequestError,
    FollowUpAction,
    FollowUpStatus,
    FollowUpWorkflow,
    InvalidTransitionError,
    SharedSnapshot,
)
from ..domain.metrics import DataProvenance, MetricKey
from ..domain.units import format_number
from ..domain.visit_prep import SUMMARY_METRIC_ORDER
from ..errors import bad_request, conflict, forbidden, not_found
from ..schemas.api import FollowUpCreate
from ..services import notifications as notify
from ..services.report_service import cgm_report_from_record

router = APIRouter(prefix="/followups", tags=["followups"])

workflow = FollowUpWorkflow()


def _snapshot_for(rec, include_metrics: bool) -> SharedSnapshot:
    report = cgm_report_from_record(rec)
    period = report.effective_period
    from ..domain.units import ar_period
    label = ar_period(period.start, period.end) if period else "فترة غير محددة"
    items: dict[str, str] = {}
    if include_metrics:
        for k in SUMMARY_METRIC_ORDER:
            v = report.verified_value(k)
            if v is None:
                continue
            m = report.metric(k)
            suffix = "%" if m.unit == "%" else f" {m.unit}"
            items[k.label_ar] = f"{format_number(v)}{suffix}"
    notes = list(report.quality.reasons_ar)
    if rec.format_id:
        notes.append(f"تنسيق التقرير: {rec.format_id}"
                     + ("" if rec.format_verified else " (تنسيق غير مُتحقَّق منه)"))
    return SharedSnapshot(period_label=label, items=items, quality_notes_ar=notes)


@router.get("")
def list_followups(session: Session = Depends(get_session)) -> dict:
    rows = session.repo.list_followups(session.user_id)
    return {"items": [f.to_json() for f in rows], "total": len(rows)}


@router.post("", status_code=201)
def create_followup(body: FollowUpCreate, session: Session = Depends(get_session)) -> dict:
    rule_ids: list[str] = []
    snapshot = SharedSnapshot(period_label="بدون تقرير", items={}, quality_notes_ar=[])
    rec = None

    if body.report_id:
        rec = session.repo.get_report(session.user_id, body.report_id)
        if rec is None:
            raise not_found("لم نعثر على هذا التقرير ضمن تقاريرك.")
        if rec.status not in ("ready", "needs_review"):
            raise bad_request("report_not_ready", "انتظر اكتمال التقرير بنجاح قبل إرسال طلب متابعة.")
        analysis = rec.analysis or {}
        rule_ids = [r["rule_id"] for r in analysis.get("results", []) if r.get("status") == "triggered"]
        snapshot = _snapshot_for(rec, body.include_metrics)

    actor = Actor(session.user_id, session.role)
    existing = session.repo.list_followups(session.user_id)
    try:
        request = workflow.create_draft(
            id=new_id(), pseudo_ref=new_pseudo("REQ"), user_id=session.user_id,
            trigger=body.trigger, rule_ids=rule_ids,
            rules_version=(rec.analysis or {}).get("rules_version", "n/a") if rec else "n/a",
            reason_ar=body.reason_ar.strip(), snapshot=snapshot, now=now_utc(),
            existing=existing,
            provenance=DataProvenance.SYNTHETIC if session.is_demo else DataProvenance.REAL,
            report_id=body.report_id,
        )
    except DuplicateRequestError as exc:
        raise conflict("duplicate_request", exc.message_ar) from None

    try:
        session.repo.create_followup(request)
    except DuplicateRequestError as exc:
        raise conflict("duplicate_request", exc.message_ar) from None

    if body.submit_now:
        try:
            request = workflow.submit(request, actor, now_utc())
        except InvalidTransitionError as exc:
            raise bad_request("invalid_transition", exc.message_ar) from None
        session.repo.save_followup(request)
        notify.followup_submitted(session.repo, request)

    return request.to_json()


def _owned(session: Session, request_id: str):
    f = session.repo.get_followup(request_id)
    if f is None:
        raise not_found("لم نعثر على طلب المتابعة.")
    actor = Actor(session.user_id, session.role)
    if not workflow.policy.can(actor, FollowUpAction.VIEW, f):
        raise forbidden()
    return f, actor


@router.get("/{request_id}")
def get_followup(request_id: str, session: Session = Depends(get_session)) -> dict:
    f, _ = _owned(session, request_id)
    appointment = session.repo.appointment_for_followup(f.id)
    payload = f.to_json()
    payload["appointment"] = appointment.to_json() if appointment else None
    return payload


@router.post("/{request_id}/submit")
def submit_followup(request_id: str, session: Session = Depends(get_session)) -> dict:
    f, actor = _owned(session, request_id)
    try:
        f = workflow.submit(f, actor, now_utc())
    except AccessDeniedError as exc:
        raise forbidden(exc.message_ar) from None
    except InvalidTransitionError as exc:
        raise bad_request("invalid_transition", exc.message_ar) from None
    session.repo.save_followup(f)
    notify.followup_submitted(session.repo, f)
    return f.to_json()


@router.post("/{request_id}/withdraw")
def withdraw_followup(request_id: str, session: Session = Depends(get_session)) -> dict:
    f, actor = _owned(session, request_id)
    try:
        f = workflow.withdraw(f, actor, now_utc())
    except AccessDeniedError as exc:
        raise forbidden(exc.message_ar) from None
    except InvalidTransitionError as exc:
        raise bad_request("invalid_transition", exc.message_ar) from None
    session.repo.save_followup(f)
    return f.to_json()


@router.post("/{request_id}/close")
def close_followup(request_id: str, session: Session = Depends(get_session)) -> dict:
    f, actor = _owned(session, request_id)
    try:
        f = workflow.close(f, actor, now_utc())
    except AccessDeniedError as exc:
        raise forbidden(exc.message_ar) from None
    except InvalidTransitionError as exc:
        raise bad_request("invalid_transition", exc.message_ar) from None
    session.repo.save_followup(f)
    return f.to_json()
