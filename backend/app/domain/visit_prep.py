"""Appointment-preparation summary built from verified data only.

Ported and adapted from packages/sukkar_core/lib/src/summary/visit_summary.dart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .comparison import CgmPeriodComparison, compare_latest_cgm_periods
from .followup import FollowUpRequest, FollowUpStatus
from .metrics import CgmReport, MetricKey, MetricValue, TargetProfile
from .rules import RuleEngine, RuleEvaluation
from .targets import consensus_targets_for
from .units import ar_period, format_number

DISCLAIMER_AR = (
    "هذا الملخص تعليمي لمساعدتك على الاستعداد لموعدك، أعدّه نموذج أولي مستقل (سكر بلس) "
    "غير مرتبط بأي جهة صحية. لا يتضمن تشخيصًا أو توصيات علاجية أو جرعات، ولا يغني عن تقييم فريقك الصحي."
)

SUMMARY_METRIC_ORDER = [
    MetricKey.TIME_IN_RANGE,
    MetricKey.TIME_BELOW_RANGE_TOTAL,
    MetricKey.TIME_VERY_LOW,
    MetricKey.TIME_ABOVE_RANGE_TOTAL,
    MetricKey.TIME_VERY_HIGH,
    MetricKey.MEAN_GLUCOSE,
    MetricKey.GMI,
    MetricKey.CV,
    MetricKey.SENSOR_ACTIVE,
]


@dataclass(frozen=True)
class SummaryLine:
    label_ar: str
    value_ar: str
    note_ar: str | None = None
    source_ar: str | None = None

    def to_json(self) -> dict:
        return {"label_ar": self.label_ar, "value_ar": self.value_ar,
                "note_ar": self.note_ar, "source_ar": self.source_ar}


@dataclass(frozen=True)
class VisitSummary:
    generated_at: datetime
    is_synthetic: bool
    report_id: str | None
    period_ar: str | None
    period_days: int | None
    metrics: list[SummaryLine]
    patterns_ar: list[str]
    limitations_ar: list[str]
    missing_ar: list[str]
    questions_ar: list[str]
    comparison: CgmPeriodComparison | None
    outcome: RuleEvaluation | None
    target_notes_ar: list[str]
    appointment: dict | None = None
    followups: list[SummaryLine] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "is_synthetic": self.is_synthetic,
            "report_id": self.report_id,
            "period_ar": self.period_ar,
            "period_days": self.period_days,
            "metrics": [m.to_json() for m in self.metrics],
            "patterns_ar": list(self.patterns_ar),
            "limitations_ar": list(self.limitations_ar),
            "missing_ar": list(self.missing_ar),
            "questions_ar": list(self.questions_ar),
            "comparison": self.comparison.to_json() if self.comparison else None,
            "outcome": self.outcome.to_json() if self.outcome else None,
            "target_notes_ar": list(self.target_notes_ar),
            "appointment": self.appointment,
            "followups": [f.to_json() for f in self.followups],
            "disclaimer_ar": DISCLAIMER_AR,
        }


def _metric_value_ar(m: MetricValue) -> str:
    if m.value is None:
        return "غير متاح"
    suffix = "%" if m.unit == "%" else f" {m.unit}"
    return f"{format_number(m.value, 1)}{suffix}"


class VisitSummaryBuilder:
    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self.rule_engine = rule_engine or RuleEngine()

    def build(
        self, *, now: datetime, reports: list[CgmReport], followups: list[FollowUpRequest],
        appointment: dict | None, target_profile: TargetProfile,
        report: CgmReport | None = None,
    ) -> VisitSummary:
        dated = [r for r in reports if r.effective_period is not None]
        dated.sort(key=lambda r: r.effective_period.end)
        latest = report or (dated[-1] if dated else (reports[-1] if reports else None))

        missing: list[str] = []
        metrics: list[SummaryLine] = []
        patterns: list[str] = []
        limitations: list[str] = []

        if latest is None:
            missing.append("لا يوجد تقرير حساس موثّق.")
        else:
            targets = consensus_targets_for(target_profile)
            for k in SUMMARY_METRIC_ORDER:
                m = latest.metrics.get(k)
                if m is None or not m.is_verified:
                    metrics.append(SummaryLine(k.label_ar, "غير متاح"))
                    missing.append(f'لم تتوفر قيمة موثّقة لـ "{k.label_ar}".')
                    continue
                spec = targets[k] if not targets.is_empty else None
                note = m.origin.label_ar
                source = None
                if m.source_label:
                    page = f" — صفحة {m.source_page}" if m.source_page else ""
                    source = f"{m.source_label}{page}"
                metrics.append(SummaryLine(k.label_ar, _metric_value_ar(m), note_ar=note, source_ar=source))
                if spec is not None and m.value is not None and not spec.is_met_by(m.value):
                    patterns.append(
                        f"{k.label_ar} {format_number(m.value)}% لا يستوفي الهدف المرجعي العام ({spec.text_ar}).")

            limitations.extend(latest.quality.reasons_ar)
            limitations.extend(latest.warnings_ar)
            if not latest.has_raw_readings:
                limitations.append(
                    "التقرير يحتوي ملخصات مطبوعة فقط، لذلك لا يمكن تحليل أنماط الساعات أو النوبات التفصيلية.")

        comparison = compare_latest_cgm_periods(reports)
        if not comparison.comparable and comparison.reason_ar:
            missing.append(comparison.reason_ar)

        evaluation = None
        if latest is not None:
            evaluation = self.rule_engine.evaluate(latest, profile=target_profile, now=now)

        followup_lines = [
            SummaryLine(f"طلب {f.pseudo_ref}", f.status.label_ar,
                        note_ar=f.decision.label_ar if f.decision else None)
            for f in followups
        ]

        questions = generate_questions(
            latest=latest, evaluation=evaluation, comparison=comparison,
            has_appointment=appointment is not None, followups=followups,
            target_profile=target_profile,
        )

        period = latest.effective_period if latest else None
        return VisitSummary(
            generated_at=now,
            is_synthetic=any(r.provenance.value == "synthetic" for r in reports),
            report_id=latest.id if latest else None,
            period_ar=ar_period(period.start, period.end) if period else None,
            period_days=period.days if period else None,
            metrics=metrics,
            patterns_ar=list(dict.fromkeys(patterns)),
            limitations_ar=list(dict.fromkeys(limitations)),
            missing_ar=list(dict.fromkeys(missing)),
            questions_ar=questions,
            comparison=comparison,
            outcome=evaluation,
            target_notes_ar=consensus_targets_for(target_profile).notes_ar,
            appointment=appointment,
            followups=followup_lines,
        )


def generate_questions(
    *, latest: CgmReport | None, evaluation: RuleEvaluation | None,
    comparison: CgmPeriodComparison, has_appointment: bool,
    followups: list[FollowUpRequest], target_profile: TargetProfile,
) -> list[str]:
    """Neutral questions the user may choose to ask. They depend only on which
    data exist; they never contain values that are not verified."""
    q: list[str] = []
    if latest is not None and not latest.quality.sufficient:
        q.append("هل فترة بيانات الحساس كافية لتقييم الأنماط، أم أحتاج فترة أطول قبل الموعد القادم؟")
    if latest is not None and latest.verified_value(MetricKey.GMI) is not None:
        q.append("كيف تقارن قيمة GMI من تقرير الحساس بآخر نتيجة HbA1c لدي؟")
    if comparison.comparable and comparison.deltas:
        q.append("كيف أفهم الفرق بين فترتي التقريرين، وهل التغيّر ذو معنى؟")
    elif comparison.reason_ar:
        q.append("ما الذي يلزم كي تصبح تقاريري قابلة للمقارنة عبر الزمن؟")
    if evaluation is not None and evaluation.triggered:
        q.append("ما المعلومات الإضافية التي تساعد في فهم الأنماط التي ظهرت في تقريري؟")
    if has_appointment:
        q.append("هل توجد تحاليل أو فحوصات مطلوبة قبل الموعد؟")
    if target_profile in (TargetProfile.UNSPECIFIED, TargetProfile.PREGNANCY, TargetProfile.PEDIATRIC):
        q.append("ما الأهداف المناسبة لي لنطاقات السكر؟")
    else:
        q.append("هل الأهداف المرجعية العامة لنطاقات السكر مناسبة لي أم تحتاج إلى تخصيص؟")
    if any(f.status not in (FollowUpStatus.CLOSED, FollowUpStatus.DRAFT) for f in followups):
        q.append("هل يمكن مناقشة البيانات التي دفعتني إلى طلب مراجعة عبر التطبيق؟")
    return list(dict.fromkeys(q))
