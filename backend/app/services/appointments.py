"""Simulated appointment creation.

Appointments created by this prototype are always flagged `is_simulated` and
labelled as such in every response. Nothing here books a real appointment in
any clinic, hospital or national platform.
"""

from __future__ import annotations

from datetime import timedelta

from ..db.models import AppointmentRecord
from ..db.repository import Repository, new_id, now_utc
from ..domain.followup import FollowUpRequest

SIMULATED_CLINIC_AR = "عيادة السكري (محاكاة داخل النموذج الأولي)"
SIMULATED_SPECIALTY_AR = "استشارة متابعة السكري"
DEFAULT_LEAD_DAYS = 10


def create_simulated_appointment(repo: Repository, f: FollowUpRequest,
                                 lead_days: int = DEFAULT_LEAD_DAYS, persist: bool = True) -> AppointmentRecord:
    """Idempotent: one simulated appointment per approved follow-up request."""
    existing = repo.appointment_for_followup(f.id)
    if existing is not None:
        return existing

    scheduled = (now_utc() + timedelta(days=lead_days)).replace(
        hour=10, minute=30, second=0, microsecond=0)
    appointment = AppointmentRecord(
        id=new_id(), user_id=f.user_id, scheduled_at=scheduled,
        clinic_label=SIMULATED_CLINIC_AR, specialty_ar=SIMULATED_SPECIALTY_AR,
        is_simulated=True, status="upcoming", source="prototype",
        followup_id=f.id, report_id=f.report_id,
        created_at=now_utc(), provenance="synthetic",
    )
    return repo.create_appointment(appointment) if persist else appointment
