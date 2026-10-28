"""Versioned, documented rule set and the deterministic rule engine.

Ported from packages/sukkar_core/lib/src/rules/rules.dart.

Every rule is a demonstration rule: thresholds reuse the published general
reference targets where possible, but using them to trigger a review task has
not been clinically validated. A flag is not a diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .metrics import CgmReport, DataQuality, MetricKey, TargetProfile
from .targets import TargetSet, consensus_targets_for
from .units import format_number


class RuleApproval(str, Enum):
    DEMONSTRATION_ONLY = "demonstration_only"
    CLINICALLY_APPROVED = "clinically_approved"


class RuleKind(str, Enum):
    TARGET_EXCEEDANCE = "target_exceedance"
    EPISODE_COUNT = "episode_count"


class RuleStatus(str, Enum):
    TRIGGERED = "triggered"
    NOT_TRIGGERED = "not_triggered"
    NOT_ASSESSABLE = "not_assessable"
    NOT_APPLICABLE = "not_applicable"


class ReviewOutcome(str, Enum):
    """The four user-facing outcomes. Nothing else is ever shown."""

    ROUTINE_SUMMARY = "routine_summary"
    REVIEW_SUGGESTED = "review_suggested"
    NEED_MORE_DATA = "need_more_data"
    SEEK_MEDICAL_HELP = "seek_medical_help"

    @property
    def title_ar(self) -> str:
        return {
            ReviewOutcome.ROUTINE_SUMMARY: "ملخص روتيني للموعد",
            ReviewOutcome.REVIEW_SUGGESTED: "يحتاج إلى مراجعة مختص",
            ReviewOutcome.NEED_MORE_DATA: "بيانات غير مكتملة",
            ReviewOutcome.SEEK_MEDICAL_HELP: "يرجى طلب المساعدة الطبية المناسبة",
        }[self]

    @property
    def explanation_ar(self) -> str:
        return {
            ReviewOutcome.ROUTINE_SUMMARY: (
                "عولجت البيانات المتاحة ولم تطلب أي قاعدة مُعدّة مراجعة إضافية. "
                "هذا لا يعني أن حالتك آمنة طبيًا، ولا يغني عن متابعتك المعتادة."
            ),
            ReviewOutcome.REVIEW_SUGGESTED: (
                "انطبقت قاعدة مُعدّة على بيانات موثّقة، لذا يمكنك طلب مراجعة بشرية. "
                "هذا ليس تشخيصًا ولا تقييمًا لحالة طارئة."
            ),
            ReviewOutcome.NEED_MORE_DATA: (
                "البيانات الحالية ناقصة أو غير كافية لتقييم موثوق. راجع أسباب النقص أدناه."
            ),
            ReviewOutcome.SEEK_MEDICAL_HELP: (
                "إذا كنت تشعر بقلق عاجل على صحتك، تواصل فورًا مع مقدم الرعاية أو خدمات الطوارئ "
                "(911 الرقم الموحد، أو 997 الهلال الأحمر في المملكة العربية السعودية). "
                "لا يستطيع هذا النموذج الأولي تحديد ما إذا كانت حالتك طارئة."
            ),
        }[self]


@dataclass(frozen=True)
class RuleDefinition:
    id: str
    version: int
    title_ar: str
    kind: RuleKind
    metric_description_ar: str
    observation_window_ar: str
    threshold_description_ar: str
    duplicates_policy_ar: str
    gaps_policy_ar: str
    source_ref: str
    rationale_ar: str
    approval: RuleApproval
    expected_action_ar: str
    limitations_ar: str
    metric: MetricKey | None = None
    episode_threshold_mgdl: float | None = None
    min_episode_minutes: int = 15
    min_occurrences: int = 1
    window_days: int | None = None
    min_days: int = DataQuality.MIN_DAYS
    min_coverage_percent: float = DataQuality.MIN_COVERAGE_PERCENT
    enabled: bool = True

    @property
    def approval_label_ar(self) -> str:
        return ("قاعدة عرض تجريبي — تتطلب مراجعة سريرية قبل أي استخدام فعلي"
                if self.approval is RuleApproval.DEMONSTRATION_ONLY else "قاعدة معتمدة سريريًا")

    def to_json(self) -> dict:
        return {
            "id": self.id, "version": self.version, "title_ar": self.title_ar,
            "kind": self.kind.value, "metric": self.metric.value if self.metric else None,
            "metric_description_ar": self.metric_description_ar,
            "observation_window_ar": self.observation_window_ar,
            "threshold_description_ar": self.threshold_description_ar,
            "source_ref": self.source_ref, "rationale_ar": self.rationale_ar,
            "approval": self.approval.value, "approval_label_ar": self.approval_label_ar,
            "expected_action_ar": self.expected_action_ar, "limitations_ar": self.limitations_ar,
        }


@dataclass(frozen=True)
class RuleSet:
    version: str
    rules: list[RuleDefinition]


@dataclass(frozen=True)
class RuleResult:
    rule: RuleDefinition
    status: RuleStatus
    explanation_ar: str
    evidence: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "rule_id": self.rule.id, "rule_version": self.rule.version,
            "rule_title_ar": self.rule.title_ar, "status": self.status.value,
            "explanation_ar": self.explanation_ar, "evidence": dict(self.evidence),
            "approval_label_ar": self.rule.approval_label_ar,
            "source_ref": self.rule.source_ref,
            "limitations_ar": self.rule.limitations_ar,
        }


@dataclass(frozen=True)
class RuleEvaluation:
    rules_version: str
    results: list[RuleResult]
    outcome: ReviewOutcome
    reasons_ar: list[str]
    limitations_ar: list[str]
    evaluated_at: datetime

    @property
    def triggered(self) -> list[RuleResult]:
        return [r for r in self.results if r.status is RuleStatus.TRIGGERED]

    def to_json(self) -> dict:
        return {
            "rules_version": self.rules_version,
            "outcome": self.outcome.value,
            "outcome_title_ar": self.outcome.title_ar,
            "outcome_explanation_ar": self.outcome.explanation_ar,
            "results": [r.to_json() for r in self.results],
            "reasons_ar": list(self.reasons_ar),
            "limitations_ar": list(self.limitations_ar),
            "evaluated_at": self.evaluated_at.isoformat(),
        }


_DUP_POLICY = "تُحذف القراءات المكررة بنفس التوقيت؛ وعند اختلاف القيم يُحتفظ بالأولى وتُسجَّل كملاحظة جودة."
_GAP_POLICY_METRIC = "يعتمد على النسبة المطبوعة أو المحسوبة؛ لا تُملأ الفجوات بقيم تقديرية."
_GAP_POLICY_EPISODES = "لا تُدمج النوبات عبر فجوة بيانات أطول من ضعف فاصل القراءات (10 دقائق)."
_CONSENSUS = "Battelino et al., Diabetes Care 2019;42:1593-1603 (Tables 2-3)"
_DEMO_LIMIT = (
    "استخدام تجاوز الهدف المرجعي العام كمحفّز لطلب مراجعة هو اختيار تصميمي للعرض، "
    "وليس معيار فرز سريري معتمدًا. لا يقيّم الحالات الطارئة."
)

DEFAULT_RULE_SET = RuleSet(
    version="2026.10-demo.1",
    rules=[
        RuleDefinition(
            id="TBR54-TARGET", version=1,
            title_ar="الوقت أقل من 54 ملغم/دل أعلى من الهدف المرجعي العام",
            kind=RuleKind.TARGET_EXCEEDANCE, metric=MetricKey.TIME_VERY_LOW,
            metric_description_ar="نسبة الوقت أقل من 54 mg/dL (موثّقة).",
            observation_window_ar="فترة المؤشرات في التقرير.",
            threshold_description_ar="لا يستوفي الهدف المرجعي للفئة المختارة (للبالغين: أقل من 1%).",
            duplicates_policy_ar=_DUP_POLICY, gaps_policy_ar=_GAP_POLICY_METRIC,
            source_ref=_CONSENSUS,
            rationale_ar="هدف مرجعي منشور في الإجماع الدولي حول الوقت ضمن النطاق.",
            approval=RuleApproval.DEMONSTRATION_ONLY,
            expected_action_ar="اقتراح طلب مراجعة بشرية تجريبية فقط.",
            limitations_ar=_DEMO_LIMIT,
        ),
        RuleDefinition(
            id="TBR70-TARGET", version=1,
            title_ar="إجمالي الوقت أقل من 70 ملغم/دل أعلى من الهدف المرجعي العام",
            kind=RuleKind.TARGET_EXCEEDANCE, metric=MetricKey.TIME_BELOW_RANGE_TOTAL,
            metric_description_ar="نسبة الوقت أقل من 70 mg/dL (المستويان 1 و2، موثّقة أو محسوبة من فئتين موثّقتين).",
            observation_window_ar="فترة المؤشرات في التقرير.",
            threshold_description_ar=(
                "لا يستوفي الهدف المرجعي للفئة المختارة (للبالغين: أقل من 4%؛ لكبار السن/الأعلى خطورة: أقل من 1%)."),
            duplicates_policy_ar=_DUP_POLICY, gaps_policy_ar=_GAP_POLICY_METRIC,
            source_ref=_CONSENSUS,
            rationale_ar="هدف مرجعي منشور في الإجماع الدولي حول الوقت ضمن النطاق.",
            approval=RuleApproval.DEMONSTRATION_ONLY,
            expected_action_ar="اقتراح طلب مراجعة بشرية تجريبية فقط.",
            limitations_ar=_DEMO_LIMIT,
        ),
        RuleDefinition(
            id="TAR250-TARGET", version=1,
            title_ar="الوقت أعلى من 250 ملغم/دل أعلى من الهدف المرجعي العام",
            kind=RuleKind.TARGET_EXCEEDANCE, metric=MetricKey.TIME_VERY_HIGH,
            metric_description_ar="نسبة الوقت أعلى من 250 mg/dL (موثّقة).",
            observation_window_ar="فترة المؤشرات في التقرير.",
            threshold_description_ar=(
                "لا يستوفي الهدف المرجعي للفئة المختارة (للبالغين: أقل من 5%؛ لكبار السن/الأعلى خطورة: أقل من 10%)."),
            duplicates_policy_ar=_DUP_POLICY, gaps_policy_ar=_GAP_POLICY_METRIC,
            source_ref=_CONSENSUS,
            rationale_ar="هدف مرجعي منشور في الإجماع الدولي حول الوقت ضمن النطاق.",
            approval=RuleApproval.DEMONSTRATION_ONLY,
            expected_action_ar="اقتراح طلب مراجعة بشرية تجريبية فقط.",
            limitations_ar=_DEMO_LIMIT,
        ),
        RuleDefinition(
            id="EPI54-REPEATED", version=1,
            title_ar="نوبات متكررة أقل من 54 ملغم/دل في القراءات التفصيلية",
            kind=RuleKind.EPISODE_COUNT, episode_threshold_mgdl=54,
            min_episode_minutes=15, min_occurrences=2, window_days=14,
            metric_description_ar=(
                "عدد النوبات التي بقيت فيها القراءات أقل من 54 mg/dL مدة 15 دقيقة متصلة على الأقل."),
            observation_window_ar="آخر 14 يومًا من القراءات التفصيلية.",
            threshold_description_ar="نوبتان أو أكثر (عدد تجريبي قابل للتعديل، غير مستمد من مصدر).",
            duplicates_policy_ar=_DUP_POLICY, gaps_policy_ar=_GAP_POLICY_EPISODES,
            source_ref=(
                "تعريف مدة النوبة (15 دقيقة) من الإجماع الدولي 2017 المشار إليه في الجدول 1 من ورقة 2019؛ "
                "عدد النوبات (2) قيمة تجريبية."),
            rationale_ar="تكرار انخفاض السكر عن 54 أمر يستحق النقاش، لكن العدد المختار هنا للعرض فقط.",
            approval=RuleApproval.DEMONSTRATION_ONLY,
            expected_action_ar="اقتراح طلب مراجعة بشرية تجريبية فقط.",
            limitations_ar=(
                "تتطلب قراءات تفصيلية بتوقيتات؛ لا تنطبق على ملفات PDF التي تحتوي ملخصات فقط. "
                "لا تقيّم الحالات الطارئة."),
        ),
    ],
)


class RuleEngine:
    def __init__(self, rule_set: RuleSet = DEFAULT_RULE_SET) -> None:
        self.rule_set = rule_set

    def evaluate(self, report: CgmReport, profile: TargetProfile, now: datetime) -> RuleEvaluation:
        targets = consensus_targets_for(profile)
        results: list[RuleResult] = []
        limitations: list[str] = []

        for rule in (r for r in self.rule_set.rules if r.enabled):
            if rule.kind is RuleKind.TARGET_EXCEEDANCE:
                results.append(self._eval_target(rule, report, targets))
            else:
                results.append(self._eval_episodes(rule, report))

        for r in results:
            if r.status is RuleStatus.NOT_APPLICABLE:
                limitations.append(r.explanation_ar)

        triggered = [r for r in results if r.status is RuleStatus.TRIGGERED]
        not_assessable = [r for r in results if r.status is RuleStatus.NOT_ASSESSABLE]

        reasons: list[str] = []
        if triggered:
            outcome = ReviewOutcome.REVIEW_SUGGESTED
            reasons.extend(r.explanation_ar for r in triggered)
            if not_assessable:
                reasons.append("تعذّر تقييم بعض القواعد الأخرى بسبب نقص البيانات.")
        elif not_assessable or not report.quality.sufficient:
            outcome = ReviewOutcome.NEED_MORE_DATA
            reasons.extend(report.quality.reasons_ar)
            reasons.extend(dict.fromkeys(r.explanation_ar for r in not_assessable))
        else:
            outcome = ReviewOutcome.ROUTINE_SUMMARY

        return RuleEvaluation(
            rules_version=self.rule_set.version, results=results, outcome=outcome,
            reasons_ar=list(dict.fromkeys(reasons)), limitations_ar=limitations, evaluated_at=now,
        )

    @staticmethod
    def urgent_concern_outcome() -> ReviewOutcome:
        """Only ever called when the user explicitly reports an urgent concern.
        The response is general safety messaging; no assessment is attempted."""
        return ReviewOutcome.SEEK_MEDICAL_HELP

    @staticmethod
    def _quality_gate(rule: RuleDefinition, report: CgmReport) -> str | None:
        q = report.quality
        if q.days_of_data is None or q.days_of_data < rule.min_days:
            return f"مدة البيانات أقل من {rule.min_days} يومًا أو غير معروفة."
        if q.coverage_percent is None or q.coverage_percent < rule.min_coverage_percent:
            return f"تغطية بيانات الحساس أقل من {format_number(rule.min_coverage_percent)}% أو غير مؤكدة."
        return None

    def _eval_target(self, rule: RuleDefinition, report: CgmReport, targets: TargetSet) -> RuleResult:
        key = rule.metric
        if targets.is_empty:
            return RuleResult(
                rule=rule, status=RuleStatus.NOT_ASSESSABLE,
                explanation_ar=(
                    f"لا توجد أهداف مرجعية مطبّقة للفئة المختارة ({targets.profile.label_ar})؛ "
                    "نحتاج أهدافًا من الفريق الصحي."),
            )
        spec = targets[key]
        if spec is None:
            return RuleResult(
                rule=rule, status=RuleStatus.NOT_APPLICABLE,
                explanation_ar=f'لا يحدد الإجماع هدفًا عامًا منفصلًا لـ "{key.label_ar}" لهذه الفئة.',
            )
        gate = self._quality_gate(rule, report)
        if gate:
            return RuleResult(rule=rule, status=RuleStatus.NOT_ASSESSABLE,
                              explanation_ar=f"{rule.title_ar}: {gate}")
        v = report.verified_value(key)
        if v is None:
            return RuleResult(rule=rule, status=RuleStatus.NOT_ASSESSABLE,
                              explanation_ar=f'"{key.label_ar}" غير متاح أو غير موثّق.')

        evidence = {key.label_ar: f"{format_number(v)}%", "الهدف المرجعي العام": spec.text_ar}
        if spec.is_met_by(v):
            return RuleResult(
                rule=rule, status=RuleStatus.NOT_TRIGGERED,
                explanation_ar=f"{key.label_ar} {format_number(v)}% ضمن الهدف المرجعي العام ({spec.text_ar}).",
                evidence=evidence,
            )
        return RuleResult(
            rule=rule, status=RuleStatus.TRIGGERED,
            explanation_ar=(
                f"{key.label_ar} {format_number(v)}% لا يستوفي الهدف المرجعي العام ({spec.text_ar}) "
                f"— قاعدة {rule.id} v{rule.version}."),
            evidence=evidence,
        )

    def _eval_episodes(self, rule: RuleDefinition, report: CgmReport) -> RuleResult:
        if not report.has_raw_readings:
            return RuleResult(
                rule=rule, status=RuleStatus.NOT_APPLICABLE,
                explanation_ar=(
                    "لا يمكن تقييم النوبات المتكررة لعدم توفر قراءات تفصيلية بتوقيتاتها في هذا التقرير."),
            )
        return RuleResult(rule=rule, status=RuleStatus.NOT_ASSESSABLE,
                          explanation_ar=f"{rule.title_ar}: لم تُحمَّل قراءات تفصيلية.")
