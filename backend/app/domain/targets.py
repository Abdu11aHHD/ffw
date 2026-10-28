"""General reference targets from the 2019 International Consensus on Time in Range.

Ported from packages/sukkar_core/lib/src/cgm/targets.dart.
These are population-level reference targets, not personalised goals, and are
only displayed for the profile they belong to.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .metrics import MetricKey, TargetProfile

T3 = "Battelino et al., Diabetes Care 2019;42:1593-1603, Table 3"
T2 = "Battelino et al., Diabetes Care 2019;42:1593-1603, Table 2"


class TargetComparator(str, Enum):
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    LESS_OR_EQUAL = "less_or_equal"


@dataclass(frozen=True)
class TargetSpec:
    key: MetricKey
    comparator: TargetComparator
    value: float
    source_ref: str

    def is_met_by(self, v: float) -> bool:
        if self.comparator is TargetComparator.GREATER_THAN:
            return v > self.value
        if self.comparator is TargetComparator.LESS_THAN:
            return v < self.value
        return v <= self.value

    @property
    def text_ar(self) -> str:
        op = {
            TargetComparator.GREATER_THAN: "أكثر من",
            TargetComparator.LESS_THAN: "أقل من",
            TargetComparator.LESS_OR_EQUAL: "لا يزيد على",
        }[self.comparator]
        v = int(self.value) if self.value == int(self.value) else self.value
        return f"{op} {v}%"


@dataclass(frozen=True)
class TargetSet:
    profile: TargetProfile
    targets: dict[MetricKey, TargetSpec]
    notes_ar: list[str]

    @property
    def is_empty(self) -> bool:
        return not self.targets

    def __getitem__(self, k: MetricKey) -> TargetSpec | None:
        return self.targets.get(k)


_GENERAL_ADULT = TargetSet(
    TargetProfile.GENERAL_ADULT_T1_T2,
    {
        MetricKey.TIME_IN_RANGE: TargetSpec(MetricKey.TIME_IN_RANGE, TargetComparator.GREATER_THAN, 70, T3),
        MetricKey.TIME_BELOW_RANGE_TOTAL: TargetSpec(MetricKey.TIME_BELOW_RANGE_TOTAL, TargetComparator.LESS_THAN, 4, T3),
        MetricKey.TIME_VERY_LOW: TargetSpec(MetricKey.TIME_VERY_LOW, TargetComparator.LESS_THAN, 1, T3),
        MetricKey.TIME_ABOVE_RANGE_TOTAL: TargetSpec(MetricKey.TIME_ABOVE_RANGE_TOTAL, TargetComparator.LESS_THAN, 25, T3),
        MetricKey.TIME_VERY_HIGH: TargetSpec(MetricKey.TIME_VERY_HIGH, TargetComparator.LESS_THAN, 5, T3),
        MetricKey.CV: TargetSpec(MetricKey.CV, TargetComparator.LESS_OR_EQUAL, 36, T2),
    },
    [
        "أهداف مرجعية عامة لكثير من البالغين المصابين بالسكري من النوع الأول أو الثاني، وليست أهدافًا شخصية.",
        "يذكر الإجماع أنه لمن هم دون 25 عامًا، إذا كان هدف HbA1c هو 7.5%، يُضبط هدف TIR عند 60% تقريبًا — راجع فريقك الصحي.",
    ],
)

_OLDER = TargetSet(
    TargetProfile.OLDER_OR_HIGH_RISK,
    {
        MetricKey.TIME_IN_RANGE: TargetSpec(MetricKey.TIME_IN_RANGE, TargetComparator.GREATER_THAN, 50, T3),
        MetricKey.TIME_BELOW_RANGE_TOTAL: TargetSpec(MetricKey.TIME_BELOW_RANGE_TOTAL, TargetComparator.LESS_THAN, 1, T3),
        MetricKey.TIME_VERY_HIGH: TargetSpec(MetricKey.TIME_VERY_HIGH, TargetComparator.LESS_THAN, 10, T3),
        MetricKey.CV: TargetSpec(MetricKey.CV, TargetComparator.LESS_OR_EQUAL, 36, T2),
    },
    ["أهداف مرجعية عامة لكبار السن أو الفئات الأعلى خطورة وفق الإجماع، وتحتاج إلى تخصيص من الفريق الصحي."],
)

_PREGNANCY = TargetSet(
    TargetProfile.PREGNANCY,
    {},
    ["تستخدم أهداف الحمل نطاقات سكر مختلفة (63–140 mg/dL) ولا يطبّقها التطبيق تلقائيًا. اطلبي الأهداف من فريقك الصحي."],
)

_PEDIATRIC = TargetSet(
    TargetProfile.PEDIATRIC,
    {},
    ["أهداف الأطفال واليافعين تُحدَّد مع الفريق الصحي ولا يطبّقها التطبيق تلقائيًا."],
)

_UNSPECIFIED = TargetSet(
    TargetProfile.UNSPECIFIED,
    {},
    ["لم تُحدَّد الفئة المرجعية، لذلك لا تُعرض أهداف عامة. يمكنك اختيارها من الملف الشخصي بعد التأكد مع فريقك الصحي."],
)

_BY_PROFILE = {
    TargetProfile.GENERAL_ADULT_T1_T2: _GENERAL_ADULT,
    TargetProfile.OLDER_OR_HIGH_RISK: _OLDER,
    TargetProfile.PREGNANCY: _PREGNANCY,
    TargetProfile.PEDIATRIC: _PEDIATRIC,
    TargetProfile.UNSPECIFIED: _UNSPECIFIED,
}


def consensus_targets_for(profile: TargetProfile) -> TargetSet:
    """Pregnancy, pediatric and unspecified profiles return an empty set:
    those targets must come from the care team."""
    return _BY_PROFILE[profile]
