"""The الرئيسية screen aggregate and the Sukkar Plus service state."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db.models import ReportStatus
from ..db.repository import now_utc
from ..deps import Session, get_session
from ..domain.followup import FollowUpStatus

router = APIRouter(tags=["home"])


JOURNEY_STATES = {
    "no_report": ("لم ترفع تقريرًا بعد", "ابدأ برفع تقرير السكر لنرتّبه معك خطوة بخطوة."),
    "processing": ("جارٍ تجهيز تقريرك", "نقرأ الملف ونستخرج المؤشرات المطبوعة. لن يستغرق الأمر طويلًا."),
    "needs_review": ("تقريرك يحتاج مراجعتك", "بعض القيم تحتاج تأكيدك قبل اعتمادها في الملخص."),
    "ready": ("التقرير جاهز للمراجعة", "اطّلع على المؤشرات ومصادرها، وجهّز أسئلتك للموعد."),
    "failed": ("تعذّرت معالجة التقرير", "راجع سبب التعذّر وجرّب رفع ملف PDF نصي من تطبيق الحساس."),
    "followup_pending": ("لديك طلب متابعة قيد المراجعة", "سنخبرك فور صدور قرار المراجع التجريبي."),
    "followup_reviewed": ("تمت مراجعة طلبك", "اطّلع على القرار وملاحظات المراجع التجريبي."),
    "appointment_ready": ("موعدك التجريبي جاهز", "راجع تفاصيل الموعد وملخص الاستعداد قبله."),
}


def _journey(session: Session) -> dict:
    reports, total = session.repo.list_reports(session.user_id, limit=1)
    followups = session.repo.list_followups(session.user_id)
    appointments = [a for a in session.repo.list_appointments(session.user_id)
                    if a.scheduled_at >= now_utc()]

    latest = reports[0] if reports else None
    key = "no_report"
    if appointments and any(a.source == "prototype" for a in appointments):
        key = "appointment_ready"
    elif any(f.status is FollowUpStatus.REVIEWED for f in followups):
        key = "followup_reviewed"
    elif any(f.status in (FollowUpStatus.AWAITING_REVIEW, FollowUpStatus.UNDER_REVIEW,
                          FollowUpStatus.MORE_INFO_REQUESTED) for f in followups):
        key = "followup_pending"
    elif latest is not None:
        key = {
            ReportStatus.PROCESSING: "processing",
            ReportStatus.NEEDS_REVIEW: "needs_review",
            ReportStatus.READY: "ready",
            ReportStatus.FAILED: "failed",
        }.get(latest.status, "no_report")

    title, body = JOURNEY_STATES[key]
    steps = [
        {"key": "upload", "label_ar": "رفع التقرير",
         "done": total > 0},
        {"key": "process", "label_ar": "قراءة المؤشرات",
         "done": latest is not None and latest.status in (ReportStatus.READY, ReportStatus.NEEDS_REVIEW)},
        {"key": "prepare", "label_ar": "الاستعداد للموعد",
         "done": latest is not None and bool(latest.verified_metrics)},
        {"key": "followup", "label_ar": "طلب متابعة",
         "done": any(f.status is not FollowUpStatus.DRAFT for f in followups)},
        {"key": "appointment", "label_ar": "موعد تجريبي",
         "done": any(a.source == "prototype" for a in appointments)},
    ]
    return {
        "state": key, "title_ar": title, "body_ar": body,
        "steps": steps,
        "reports_count": total,
        "latest_report": latest.summary_json() if latest else None,
    }


@router.get("/home")
def home(session: Session = Depends(get_session)) -> dict:
    appointments = session.repo.list_appointments(session.user_id)
    upcoming = [a for a in appointments if a.scheduled_at >= now_utc()]
    notifications = session.repo.list_notifications(session.user_id)
    unread = sum(1 for n in notifications if n.read_at is None)
    journey = _journey(session)

    return {
        "profile": session.profile.to_json(),
        "demo_mode": session.is_demo,
        "greeting_ar": "مرحبًا",
        "unread_notifications": unread,
        "next_appointment": upcoming[0].to_json() if upcoming else None,
        "sukkar_plus": journey,
        "shortcuts": [
            {"key": "sukkar_plus", "label_ar": "عضيد", "subtitle_ar": "رحلتك مع السكر، بطريقة أسهل",
             "route": "/my-profile/diabetes-journey", "icon": "glucose"},
            {"key": "appointments", "label_ar": "مواعيدي", "subtitle_ar": "القادمة والسابقة",
             "route": "/appointments", "icon": "calendar"},
            {"key": "wellness", "label_ar": "جودة الحياة", "subtitle_ar": "معلومات ونصائح",
             "route": "/wellness", "icon": "leaf"},
            {"key": "profile", "label_ar": "ملفي", "subtitle_ar": "ملفك الصحي وخدماتك",
             "route": "/my-profile", "icon": "user"},
        ],
    }


@router.get("/sukkar/state")
def sukkar_state(session: Session = Depends(get_session)) -> dict:
    """Everything the Sukkar Plus landing screen needs in one call."""
    followups = session.repo.list_followups(session.user_id)
    reports, total = session.repo.list_reports(session.user_id, limit=5)
    return {
        "journey": _journey(session),
        "recent_reports": [r.summary_json() for r in reports],
        "reports_total": total,
        "followups": [f.to_json() for f in followups[:5]],
        "open_followups": sum(1 for f in followups if f.status.is_open),
        "demo_mode": session.is_demo,
        "how_it_works": [
            {"step": 1, "title_ar": "ارفع تقريرك",
             "body_ar": "ملف PDF نصي مُصدَّر من تطبيق الحساس أو المضخة."},
            {"step": 2, "title_ar": "نقرأ المطبوع فقط",
             "body_ar": "نستخرج المؤشرات المطبوعة في صفحة الملخص، ونحتفظ بمصدر كل قيمة والصفحة التي جاءت منها."},
            {"step": 3, "title_ar": "نتحقق قبل أن نعرض",
             "body_ar": "فحوص حسابية تتأكد أن النطاقات تجمع 100% وأن GMI يتسق مع المتوسط."},
            {"step": 4, "title_ar": "تجهّز لموعدك",
             "body_ar": "ملخص بالعربية مع حدود البيانات وأسئلة مقترحة لفريقك الصحي."},
            {"step": 5, "title_ar": "تطلب مراجعة عند الحاجة",
             "body_ar": "طلب مراجعة تجريبي داخل النموذج الأولي — لا يصل إلى طبيب حقيقي."},
        ],
        "limits_ar": [
            "لا يتصل عضيد بأجهزة الحساس أو بالمستشفيات أو بمنصة صحتي الرسمية.",
            "لا يقدّم تشخيصًا ولا توصيات علاجية ولا أي إرشاد بشأن الجرعات.",
            "المواعيد التي تُنشأ هنا مواعيد تجريبية داخل النموذج الأولي فقط.",
        ],
    }
