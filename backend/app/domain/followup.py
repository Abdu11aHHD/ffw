"""Follow-up request state machine, access policy and idempotency.

Ported from packages/sukkar_core/lib/src/{models/followup,followup/followup_workflow}.dart.
The same transitions exist in SQL RPCs (submit_followup, reviewer_start_review,
reviewer_decide, close_followup, withdraw_followup); direct UPDATEs are not granted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .metrics import DataProvenance, UserRole

DEMO_REVIEWER_LABEL = "مراجع تجريبي (ليس طبيبًا حقيقيًا)"


class FollowUpStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_REVIEW = "awaiting_review"
    UNDER_REVIEW = "under_review"
    MORE_INFO_REQUESTED = "more_info_requested"
    REVIEWED = "reviewed"
    CLOSED = "closed"

    @property
    def label_ar(self) -> str:
        return {
            FollowUpStatus.DRAFT: "مسودة",
            FollowUpStatus.AWAITING_REVIEW: "بانتظار المراجعة",
            FollowUpStatus.UNDER_REVIEW: "قيد المراجعة",
            FollowUpStatus.MORE_INFO_REQUESTED: "مطلوب معلومات إضافية",
            FollowUpStatus.REVIEWED: "تمت المراجعة",
            FollowUpStatus.CLOSED: "مغلق",
        }[self]

    @property
    def is_open(self) -> bool:
        return self is not FollowUpStatus.CLOSED


class ReviewDecision(str, Enum):
    """Simulated reviewer decisions. None books a real appointment or changes treatment."""

    REVIEW_REQUIRED = "review_required"
    DATA_COMPLETION = "data_completion"
    NO_FURTHER_ACTION_DEMO = "no_further_action_demo"

    @property
    def label_ar(self) -> str:
        return {
            ReviewDecision.REVIEW_REQUIRED: "مراجعة مطلوبة",
            ReviewDecision.DATA_COMPLETION: "استكمال البيانات",
            ReviewDecision.NO_FURTHER_ACTION_DEMO: "لا إجراء إضافي (عرض تجريبي)",
        }[self]

    @property
    def patient_message_ar(self) -> str:
        return {
            ReviewDecision.REVIEW_REQUIRED: (
                "أشار المراجع التجريبي إلى أن البيانات تستحق النقاش مع فريقك الصحي. "
                "هذا ليس تشخيصًا، والموعد الذي أُنشئ موعد تجريبي داخل النموذج الأولي فقط."),
            ReviewDecision.DATA_COMPLETION: "طلب المراجع التجريبي استكمال البيانات قبل المتابعة.",
            ReviewDecision.NO_FURTHER_ACTION_DEMO: "تمت مراجعة الطلب في العرض التجريبي دون إجراء إضافي.",
        }[self]

    @property
    def creates_simulated_appointment(self) -> bool:
        return self is ReviewDecision.REVIEW_REQUIRED


class FollowUpTrigger(str, Enum):
    RULE = "rule"
    USER_REQUEST = "user_request"

    @property
    def label_ar(self) -> str:
        return "قاعدة مُعدّة مسبقًا" if self is FollowUpTrigger.RULE else "طلب من المستخدم"


class FollowUpAction(str, Enum):
    VIEW = "view"
    SUBMIT = "submit"
    WITHDRAW = "withdraw"
    START_REVIEW = "start_review"
    DECIDE = "decide"
    CLOSE = "close"
    ADD_NOTE = "add_note"


# ------------------------------------------------------------- exceptions


class InvalidTransitionError(Exception):
    def __init__(self, message_ar: str) -> None:
        super().__init__(message_ar)
        self.message_ar = message_ar


class AccessDeniedError(Exception):
    def __init__(self, message_ar: str = "لا تملك صلاحية تنفيذ هذا الإجراء على الطلب.") -> None:
        super().__init__(message_ar)
        self.message_ar = message_ar


class DuplicateRequestError(Exception):
    def __init__(self, existing_id: str) -> None:
        super().__init__(f"open request {existing_id} already exists")
        self.existing_id = existing_id
        self.message_ar = "يوجد طلب متابعة مفتوح لنفس التقرير ونفس الأسباب."


# ----------------------------------------------------------------- models


@dataclass(frozen=True)
class SharedSnapshot:
    """The exact information the patient agreed to share with the reviewer.
    Reviewers see this snapshot only, not the patient's full record."""

    period_label: str
    items: dict[str, str]
    quality_notes_ar: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"period": self.period_label, "items": dict(self.items),
                "quality_notes": list(self.quality_notes_ar)}

    @classmethod
    def from_json(cls, d: dict) -> "SharedSnapshot":
        return cls(period_label=d.get("period") or "", items=dict(d.get("items") or {}),
                   quality_notes_ar=list(d.get("quality_notes") or []))


@dataclass(frozen=True)
class StatusHistoryEntry:
    from_status: FollowUpStatus | None
    to_status: FollowUpStatus
    at: datetime
    actor_role: UserRole
    note_ar: str | None = None

    def to_json(self) -> dict:
        return {
            "from_status": self.from_status.value if self.from_status else None,
            "from_label_ar": self.from_status.label_ar if self.from_status else None,
            "to_status": self.to_status.value,
            "to_label_ar": self.to_status.label_ar,
            "at": self.at.isoformat(),
            "actor_role": self.actor_role.value,
            "note_ar": self.note_ar,
        }


@dataclass(frozen=True)
class ReviewNote:
    at: datetime
    text_ar: str
    author_label: str = DEMO_REVIEWER_LABEL

    def to_json(self) -> dict:
        return {"at": self.at.isoformat(), "text_ar": self.text_ar, "author_label": self.author_label}


@dataclass(frozen=True)
class Actor:
    user_id: str
    role: UserRole


@dataclass
class FollowUpRequest:
    id: str
    pseudo_ref: str
    user_id: str
    trigger: FollowUpTrigger
    rule_ids: list[str]
    rules_version: str
    reason_ar: str
    snapshot: SharedSnapshot
    status: FollowUpStatus
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    provenance: DataProvenance
    report_id: str | None = None
    decision: ReviewDecision | None = None
    history: list[StatusHistoryEntry] = field(default_factory=list)
    notes: list[ReviewNote] = field(default_factory=list)
    appointment_id: str | None = None

    def to_json(self, *, include_user: bool = False) -> dict:
        d = {
            "id": self.id,
            "pseudo_ref": self.pseudo_ref,
            "trigger": self.trigger.value,
            "trigger_label_ar": self.trigger.label_ar,
            "rule_ids": list(self.rule_ids),
            "rules_version": self.rules_version,
            "reason_ar": self.reason_ar,
            "shared_snapshot": self.snapshot.to_json(),
            "status": self.status.value,
            "status_label_ar": self.status.label_ar,
            "decision": self.decision.value if self.decision else None,
            "decision_label_ar": self.decision.label_ar if self.decision else None,
            "patient_message_ar": self.decision.patient_message_ar if self.decision else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "provenance": self.provenance.value,
            "report_id": self.report_id,
            "appointment_id": self.appointment_id,
            "history": [h.to_json() for h in self.history],
            "notes": [n.to_json() for n in self.notes],
        }
        if include_user:
            d["user_id"] = self.user_id
        return d


def followup_idempotency_key(user_id: str, report_id: str | None,
                             trigger: FollowUpTrigger, rule_ids: list[str]) -> str:
    """One open request per user, report, trigger and rule set."""
    rules = ",".join(sorted(rule_ids))
    return f"{user_id}|{report_id or 'none'}|{trigger.value}|{rules}"


# ----------------------------------------------------------- access policy


class FollowUpAccessPolicy:
    """Mirrors the Supabase RLS policies and RPC checks:
    patients act on their own requests only; reviewers see submitted requests
    (never drafts) and only the shared snapshot."""

    def can(self, a: Actor, action: FollowUpAction, r: FollowUpRequest) -> bool:
        owner = a.role is UserRole.PATIENT and a.user_id == r.user_id
        reviewer = a.role is UserRole.REVIEWER
        if action is FollowUpAction.VIEW:
            return owner or (reviewer and r.status is not FollowUpStatus.DRAFT)
        if action in (FollowUpAction.SUBMIT, FollowUpAction.WITHDRAW):
            return owner
        if action in (FollowUpAction.START_REVIEW, FollowUpAction.DECIDE, FollowUpAction.ADD_NOTE):
            return reviewer
        if action is FollowUpAction.CLOSE:
            return owner or reviewer
        return False

    def require(self, a: Actor, action: FollowUpAction, r: FollowUpRequest) -> None:
        if not self.can(a, action, r):
            raise AccessDeniedError()


# -------------------------------------------------------------- workflow


class FollowUpWorkflow:
    """draft -submit-> awaiting_review -startReview-> under_review
    under_review -decide(data_completion)-> more_info_requested -submit-> awaiting_review
    under_review -decide(review_required | no_further_action)-> reviewed -close-> closed
    draft | awaiting_review -withdraw (patient)-> closed
    """

    def __init__(self, policy: FollowUpAccessPolicy | None = None) -> None:
        self.policy = policy or FollowUpAccessPolicy()

    def create_draft(
        self, *, id: str, pseudo_ref: str, user_id: str, trigger: FollowUpTrigger,
        rule_ids: list[str], rules_version: str, reason_ar: str, snapshot: SharedSnapshot,
        now: datetime, existing: list[FollowUpRequest], provenance: DataProvenance,
        report_id: str | None = None,
    ) -> FollowUpRequest:
        key = followup_idempotency_key(user_id, report_id, trigger, rule_ids)
        for e in existing:
            if e.idempotency_key == key and e.status.is_open:
                raise DuplicateRequestError(e.id)
        return FollowUpRequest(
            id=id, pseudo_ref=pseudo_ref, user_id=user_id, trigger=trigger,
            rule_ids=rule_ids, rules_version=rules_version, reason_ar=reason_ar,
            snapshot=snapshot, status=FollowUpStatus.DRAFT, idempotency_key=key,
            created_at=now, updated_at=now, provenance=provenance, report_id=report_id,
            history=[StatusHistoryEntry(None, FollowUpStatus.DRAFT, now, UserRole.PATIENT)],
        )

    def _move(self, r: FollowUpRequest, to: FollowUpStatus, a: Actor, now: datetime,
              note_ar: str | None = None, decision: ReviewDecision | None = None) -> FollowUpRequest:
        r.history = [*r.history, StatusHistoryEntry(r.status, to, now, a.role, note_ar)]
        r.status = to
        if decision is not None:
            r.decision = decision
        r.updated_at = now
        return r

    def submit(self, r: FollowUpRequest, a: Actor, now: datetime, note_ar: str | None = None) -> FollowUpRequest:
        self.policy.require(a, FollowUpAction.SUBMIT, r)
        if r.status not in (FollowUpStatus.DRAFT, FollowUpStatus.MORE_INFO_REQUESTED):
            raise InvalidTransitionError(f'لا يمكن إرسال طلب حالته "{r.status.label_ar}".')
        return self._move(r, FollowUpStatus.AWAITING_REVIEW, a, now, note_ar)

    def withdraw(self, r: FollowUpRequest, a: Actor, now: datetime) -> FollowUpRequest:
        self.policy.require(a, FollowUpAction.WITHDRAW, r)
        if r.status not in (FollowUpStatus.DRAFT, FollowUpStatus.AWAITING_REVIEW):
            raise InvalidTransitionError("لا يمكن سحب الطلب بعد بدء مراجعته.")
        return self._move(r, FollowUpStatus.CLOSED, a, now, "سحب المستخدم الطلب")

    def start_review(self, r: FollowUpRequest, a: Actor, now: datetime) -> FollowUpRequest:
        self.policy.require(a, FollowUpAction.START_REVIEW, r)
        if r.status is not FollowUpStatus.AWAITING_REVIEW:
            raise InvalidTransitionError("الطلب ليس بانتظار المراجعة.")
        return self._move(r, FollowUpStatus.UNDER_REVIEW, a, now)

    def decide(self, r: FollowUpRequest, a: Actor, now: datetime,
               decision: ReviewDecision, note_ar: str | None = None) -> FollowUpRequest:
        self.policy.require(a, FollowUpAction.DECIDE, r)
        if r.status is not FollowUpStatus.UNDER_REVIEW:
            raise InvalidTransitionError("يجب بدء المراجعة قبل تسجيل القرار.")
        to = (FollowUpStatus.MORE_INFO_REQUESTED
              if decision is ReviewDecision.DATA_COMPLETION else FollowUpStatus.REVIEWED)
        r = self._move(r, to, a, now, decision.label_ar, decision)
        if note_ar and note_ar.strip():
            r.notes = [*r.notes, ReviewNote(now, note_ar.strip())]
        return r

    def add_note(self, r: FollowUpRequest, a: Actor, now: datetime, text_ar: str) -> FollowUpRequest:
        self.policy.require(a, FollowUpAction.ADD_NOTE, r)
        if not text_ar or not text_ar.strip():
            raise InvalidTransitionError("الملاحظة فارغة.")
        r.notes = [*r.notes, ReviewNote(now, text_ar.strip())]
        r.updated_at = now
        return r

    def close(self, r: FollowUpRequest, a: Actor, now: datetime) -> FollowUpRequest:
        self.policy.require(a, FollowUpAction.CLOSE, r)
        if r.status is not FollowUpStatus.REVIEWED:
            raise InvalidTransitionError("يُغلق الطلب بعد مراجعته فقط.")
        return self._move(r, FollowUpStatus.CLOSED, a, now)
