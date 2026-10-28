"""Pydantic request/response models for the public API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..domain.followup import FollowUpTrigger, ReviewDecision
from ..domain.metrics import TargetProfile


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "sukkar-plus-api"
    version: str


class ConfigResponse(BaseModel):
    demo_mode: bool
    supabase_configured: bool
    gemini_configured: bool
    deepseek_configured: bool = False
    ai_provider: str = "local"
    ai_model: str | None = None
    ai_configured: bool = False
    environment: str
    max_upload_bytes: int
    accepted_mime_types: list[str]
    setup_notes_ar: list[str] = Field(default_factory=list)


class DemoSessionResponse(BaseModel):
    patient_token: str
    reviewer_token: str
    note_ar: str


class TargetProfileUpdate(BaseModel):
    target_profile: TargetProfile


class FieldUpdate(BaseModel):
    """A single extracted-value correction made by the patient."""
    metric_key: str
    corrected_value: float | None = None
    mark_unavailable: bool | None = None
    confirmed: bool | None = None


class FieldUpdateBatch(BaseModel):
    updates: list[FieldUpdate] = Field(default_factory=list)
    confirm_all_eligible: bool = False


class FollowUpCreate(BaseModel):
    report_id: str | None = None
    trigger: FollowUpTrigger = FollowUpTrigger.RULE
    reason_ar: str = Field(min_length=1, max_length=1000)
    include_metrics: bool = True
    submit_now: bool = True


class ReviewerDecisionRequest(BaseModel):
    decision: ReviewDecision
    note_ar: str | None = Field(default=None, max_length=2000)


class ReviewerNoteRequest(BaseModel):
    note_ar: str = Field(min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    ok: bool = True
    message_ar: str | None = None
    count: int | None = None
