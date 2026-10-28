"""In-app notifications generated from real backend events.

Every notification carries a deterministic `dedupe_key`, so reloading a page
or retrying a request never produces a second copy of the same event.
Clinical and appointment notifications are only ever written by the workflow
that actually performed the action.
"""

from __future__ import annotations

from ..db.models import NotificationKind, NotificationRecord
from ..db.repository import Repository, new_id, now_utc
from ..domain.followup import FollowUpRequest, ReviewDecision
from ..domain.units import ar_date


def _emit(repo: Repository, user_id: str, kind: str, title_ar: str, body_ar: str,
          dedupe_key: str, link: str | None = None,
          channel: str = "personal") -> NotificationRecord | None:
    return repo.create_notification(NotificationRecord(
        id=new_id(), user_id=user_id, kind=kind, channel=channel,
        title_ar=title_ar, body_ar=body_ar, created_at=now_utc(),
        dedupe_key=dedupe_key, link=link,
    ))


def report_ready(repo: Repository, user_id: str, report_id: str, outcome_title_ar: str | None) -> None:
    tail = f" النتيجة: {outcome_title_ar}." if outcome_title_ar else ""
    _emit(
        repo, user_id, NotificationKind.REPORT_READY,
        "تقريرك جاهز",
        f"انتهت معالجة تقرير السكر الذي رفعته، ويمكنك الآن مراجعة القيم المستخرجة ومصادرها.{tail}",
        dedupe_key=f"report_ready:{report_id}",
        link=f"/my-profile/diabetes-journey/reports/{report_id}",
    )


def report_failed(repo: Repository, user_id: str, report_id: str, error_ar: str) -> None:
    _emit(
        repo, user_id, NotificationKind.REPORT_FAILED,
        "تعذّرت معالجة التقرير", error_ar,
        dedupe_key=f"report_failed:{report_id}",
        link="/my-profile/diabetes-journey/upload",
    )


def followup_submitted(repo: Repository, f: FollowUpRequest) -> None:
    _emit(
        repo, f.user_id, NotificationKind.FOLLOWUP_SUBMITTED,
        "أُرسل طلب المتابعة",
        f"طلبك {f.pseudo_ref} بانتظار مراجعة مختص تجريبي. سنعلمك فور صدور القرار.",
        dedupe_key=f"followup_submitted:{f.id}:{len(f.history)}",
        link=f"/my-profile/diabetes-journey/followups/{f.id}",
    )


def followup_decided(repo: Repository, f: FollowUpRequest, decision: ReviewDecision) -> None:
    _emit(
        repo, f.user_id, NotificationKind.FOLLOWUP_DECIDED,
        "تمت مراجعة طلبك",
        f"القرار على الطلب {f.pseudo_ref}: {decision.label_ar}. {decision.patient_message_ar}",
        dedupe_key=f"followup_decided:{f.id}:{decision.value}",
        link=f"/my-profile/diabetes-journey/followups/{f.id}",
    )


def appointment_created(repo: Repository, user_id: str, appointment_id: str,
                        clinic_label: str, scheduled_at) -> None:
    _emit(
        repo, user_id, NotificationKind.APPOINTMENT_CREATED,
        "موعد تجريبي جاهز",
        f"أُنشئ موعد تجريبي في {clinic_label} بتاريخ {ar_date(scheduled_at.date())}. "
        "هذا موعد داخل النموذج الأولي فقط ولم يُحجز أي موعد حقيقي في أي منشأة صحية.",
        dedupe_key=f"appointment_created:{appointment_id}",
        link=f"/appointments/{appointment_id}",
    )


GENERAL_NOTICES = [
    (
        "عن عضيد",
        "عضيد نموذج أولي مستقل لمساعدتك على فهم تقارير السكر والاستعداد لموعدك. "
        "لا يرتبط بتطبيق صحتي أو بأي جهة صحية، ولا يقدّم تشخيصًا أو توصيات علاجية.",
        "general:about_sukkar_plus",
    ),
    (
        "كيف تحصل على تقرير مناسب للرفع",
        "صدّر تقرير الحساس من تطبيق الشركة المصنّعة كملف PDF نصي (وليس صورة ممسوحة)، "
        "واختر فترة لا تقل عن 14 يومًا لتكون المؤشرات قابلة للتقييم.",
        "general:how_to_export",
    ),
]


def seed_general_notices(repo: Repository, user_id: str) -> None:
    """General (non-personal) notices shown on the العامة tab."""
    for title, body, key in GENERAL_NOTICES:
        _emit(repo, user_id, NotificationKind.GENERAL, title, body,
              dedupe_key=key, channel="general")
