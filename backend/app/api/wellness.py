"""جودة الحياة - general diabetes education and appointment-preparation tips.

Content is general and evidence-informed, aimed at helping someone prepare
for a conversation with their own care team. It contains no personalised
insulin dosing, no medication changes and no treatment adjustments.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import Session, get_session
from ..domain.metrics import DataQuality

CONSENSUS_REF = "Battelino et al., Diabetes Care 2019;42:1593-1603 — الإجماع الدولي حول الوقت ضمن النطاق"

TOPICS = [
    {
        "id": "time_in_range",
        "icon": "range",
        "title_ar": "ما معنى الوقت ضمن النطاق؟",
        "summary_ar": "النسبة التي بقي فيها السكر بين 70 و180 ملغم/دل خلال فترة التقرير.",
        "body_ar": [
            "يقيس «الوقت ضمن النطاق» (TIR) نسبة القراءات التي وقعت بين 70 و180 ملغم/دل.",
            "يذكر الإجماع الدولي هدفًا مرجعيًا عامًا لكثير من البالغين يزيد على 70%، "
            "مع أقل من 4% تحت 70 ملغم/دل وأقل من 1% تحت 54 ملغم/دل.",
            "هذه أرقام مرجعية عامة للفئات المذكورة في الإجماع، وليست أهدافًا شخصية. "
            "أهدافك أنت يحددها فريقك الصحي.",
        ],
        "source_ref": CONSENSUS_REF,
    },
    {
        "id": "data_sufficiency",
        "icon": "calendar",
        "title_ar": "كم يومًا من البيانات يكفي؟",
        "summary_ar": f"{DataQuality.MIN_DAYS} يومًا على الأقل وتغطية حساس لا تقل عن {int(DataQuality.MIN_COVERAGE_PERCENT)}%.",
        "body_ar": [
            "تصبح مؤشرات الحساس أكثر تمثيلًا عندما تغطي 14 يومًا على الأقل.",
            "تحتاج أيضًا إلى تغطية جيدة داخل تلك الأيام: نسبة عمل الحساس لا تقل عن 70% تقريبًا.",
            "إذا كانت الفترة أقصر أو التغطية أقل، يعرض سكر بلس النتيجة على أنها «بيانات غير مكتملة» "
            "بدل أن يعطيك انطباعًا مطمئنًا غير دقيق.",
        ],
        "source_ref": CONSENSUS_REF,
    },
    {
        "id": "gmi_vs_hba1c",
        "icon": "lab",
        "title_ar": "الفرق بين GMI وتحليل HbA1c",
        "summary_ar": "الأول تقدير من قراءات الحساس، والثاني تحليل دم مخبري.",
        "body_ar": [
            "يُحسب مؤشر إدارة الجلوكوز (GMI) من متوسط قراءات الحساس خلال فترة التقرير.",
            "أما HbA1c فتحليل دم يعكس متوسطًا أطول ويتأثر بعوامل أخرى مثل عمر كريات الدم الحمراء.",
            "اختلاف القيمتين شائع ولا يعني بحد ذاته وجود مشكلة؛ وهو سؤال جيد تطرحه في موعدك.",
        ],
        "source_ref": "Bergenstal RM et al., Diabetes Care 2018;41:2275-2280",
    },
    {
        "id": "appointment_prep",
        "icon": "clipboard",
        "title_ar": "كيف تستعد لموعدك؟",
        "summary_ar": "جهّز تقريرك وأسئلتك قبل الموعد لتستفيد من الوقت القصير.",
        "body_ar": [
            "صدّر تقرير الحساس لفترة لا تقل عن أسبوعين قبل الموعد وارفعه في سكر بلس.",
            "راجع ملخص «الاستعداد لموعدي» واختر ثلاثة أسئلة تهمك أكثر من غيرها.",
            "دوّن ما لاحظته بنفسك: أوقات الانخفاض أو الارتفاع، تغيّرات النوم أو النشاط أو الوجبات.",
            "اذكر لفريقك الصحي أي أدوية أو مكمّلات بدأتها أو أوقفتها، وأي أعراض جديدة.",
        ],
        "source_ref": None,
    },
    {
        "id": "daily_habits",
        "icon": "heart",
        "title_ar": "عادات يومية تدعم السيطرة على السكر",
        "summary_ar": "النشاط والنوم والتغذية المتوازنة عوامل مؤثرة يناقشها فريقك الصحي معك.",
        "body_ar": [
            "النشاط البدني المنتظم والنوم الكافي والتغذية المتوازنة عوامل معروفة بتأثيرها على السكر.",
            "التغييرات الكبيرة في النشاط أو الوجبات قد تستدعي مراجعة خطتك العلاجية مع فريقك الصحي أولًا.",
            "سكر بلس لا يقترح جرعات ولا يعدّل خطة علاج، وإنما يساعدك على ملاحظة الأنماط ومناقشتها.",
        ],
        "source_ref": None,
    },
    {
        "id": "when_to_seek_help",
        "icon": "alert",
        "title_ar": "متى تطلب المساعدة الطبية فورًا؟",
        "summary_ar": "لا تنتظر مراجعة داخل التطبيق إذا شعرت بقلق عاجل على صحتك.",
        "body_ar": [
            "إذا شعرت بأعراض شديدة أو مقلقة، تواصل فورًا مع مقدم الرعاية الصحية أو خدمات الطوارئ "
            "(911 الرقم الموحد، أو 997 الهلال الأحمر في المملكة العربية السعودية).",
            "طلب المراجعة داخل سكر بلس طلب تجريبي داخل النموذج الأولي، ولا يصل إلى طبيب حقيقي، "
            "ولا يصلح للحالات العاجلة.",
            "لا يستطيع هذا النموذج الأولي تحديد ما إذا كانت حالتك طارئة.",
        ],
        "source_ref": None,
        "tone": "alert",
    },
]

router = APIRouter(prefix="/wellness", tags=["wellness"])


@router.get("")
def wellness(session: Session = Depends(get_session)) -> dict:
    rows, total = session.repo.list_reports(session.user_id, limit=1)
    latest = rows[0] if rows else None
    return {
        "topics": TOPICS,
        "linked_report": latest.summary_json() if (latest and latest.verified_metrics) else None,
        "disclaimer_ar": (
            "محتوى تعليمي عام من نموذج أولي مستقل. لا يتضمن تشخيصًا ولا توصيات علاجية "
            "ولا أي إرشاد بشأن جرعات الدواء أو الإنسولين."
        ),
    }
