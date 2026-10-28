"""Demo mode: a single, clearly-labelled synthetic patient and reviewer.

Demo data never pretends to be real. Every record created here is marked
synthetic, every appointment is marked simulated, and the API advertises
`demo_mode: true` so the website can show the "وضع العرض" banner.

The profile below is fictional. No value is taken from any real report or
from the reference screenshots.
"""

from __future__ import annotations

from datetime import timedelta

from .db.models import AppointmentRecord, ProfileRecord
from .db.repository import InMemoryRepository, new_id, now_utc
from .domain.metrics import TargetProfile, UserRole
from .services import notifications as notify

DEMO_PATIENT_ID = "11111111-1111-4111-8111-111111111111"
DEMO_REVIEWER_ID = "22222222-2222-4222-8222-222222222222"

DEMO_PATIENT_TOKEN = "demo-patient"
DEMO_REVIEWER_TOKEN = "demo-reviewer"

DEMO_TOKENS = {
    DEMO_PATIENT_TOKEN: DEMO_PATIENT_ID,
    DEMO_REVIEWER_TOKEN: DEMO_REVIEWER_ID,
}


def seed(repo: InMemoryRepository) -> None:
    if repo.get_profile(DEMO_PATIENT_ID) is not None:
        return

    repo.upsert_profile(ProfileRecord(
        id=DEMO_PATIENT_ID, pseudo_id="SP-DEMO01", role=UserRole.PATIENT,
        target_profile=TargetProfile.GENERAL_ADULT_T1_T2,
        display_name="نورة عبدالله السالم (حساب تجريبي)",
        health_record_number="SP-0000-0000-DEMO",
        is_synthetic=True,
    ))
    repo.upsert_profile(ProfileRecord(
        id=DEMO_REVIEWER_ID, pseudo_id="SP-DEMO02", role=UserRole.REVIEWER,
        target_profile=TargetProfile.UNSPECIFIED,
        display_name="مراجع تجريبي (ليس طبيبًا حقيقيًا)",
        health_record_number=None, is_synthetic=True,
    ))

    past = (now_utc() - timedelta(days=96)).replace(hour=9, minute=0, second=0, microsecond=0)
    repo.create_appointment(AppointmentRecord(
        id=new_id(), user_id=DEMO_PATIENT_ID, scheduled_at=past,
        clinic_label="عيادة السكري (محاكاة داخل النموذج الأولي)",
        specialty_ar="متابعة دورية", is_simulated=True, status="past",
        source="demo_seed", created_at=past, provenance="synthetic",
    ))

    notify.seed_general_notices(repo, DEMO_PATIENT_ID)
    notify.seed_general_notices(repo, DEMO_REVIEWER_ID)
