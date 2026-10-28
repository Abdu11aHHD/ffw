"""In-app notifications: list, read states and bulk actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..deps import Session, get_session
from ..errors import not_found
from ..schemas.api import MessageResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    channel: str | None = Query(default=None, pattern="^(personal|general)$"),
    session: Session = Depends(get_session),
) -> dict:
    rows = session.repo.list_notifications(session.user_id, channel)
    personal = session.repo.list_notifications(session.user_id, "personal")
    general = session.repo.list_notifications(session.user_id, "general")
    return {
        "items": [n.to_json() for n in rows],
        "unread_total": sum(1 for n in personal + general if n.read_at is None),
        "personal_count": len(personal),
        "personal_unread": sum(1 for n in personal if n.read_at is None),
        "general_count": len(general),
        "general_unread": sum(1 for n in general if n.read_at is None),
    }


@router.get("/{notification_id}")
def get_notification(notification_id: str, session: Session = Depends(get_session)) -> dict:
    n = session.repo.get_notification(session.user_id, notification_id)
    if n is None:
        raise not_found("لم نعثر على هذا التنبيه.")
    return n.to_json()


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, session: Session = Depends(get_session)) -> dict:
    n = session.repo.mark_notification_read(session.user_id, notification_id)
    if n is None:
        raise not_found("لم نعثر على هذا التنبيه.")
    return n.to_json()


@router.post("/read-all", response_model=MessageResponse)
def mark_all_read(session: Session = Depends(get_session)) -> MessageResponse:
    count = session.repo.mark_all_notifications_read(session.user_id)
    return MessageResponse(count=count, message_ar="تم تعليم جميع التنبيهات كمقروءة.")


@router.delete("", response_model=MessageResponse)
def delete_all(
    channel: str | None = Query(default=None, pattern="^(personal|general)$"),
    session: Session = Depends(get_session),
) -> MessageResponse:
    count = session.repo.delete_all_notifications(session.user_id, channel)
    return MessageResponse(count=count, message_ar="تم حذف التنبيهات.")
