"""Dependency injection: settings, repository, authenticated session."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, Header, Request

from .config import Settings, get_settings
from .db.models import ProfileRecord
from .db.repository import InMemoryRepository, Repository, SupabaseRepository, new_pseudo
from .domain.metrics import TargetProfile, UserRole
from .errors import forbidden, unauthorized
from .services.gemini import GeminiService
from .services.report_service import ReportProcessor

log = logging.getLogger("sukkar.deps")

_memory_repo: InMemoryRepository | None = None


def memory_repo() -> InMemoryRepository:
    global _memory_repo
    if _memory_repo is None:
        from .demo import seed
        _memory_repo = InMemoryRepository()
        seed(_memory_repo)
    return _memory_repo


def reset_memory_repo() -> InMemoryRepository:
    """Used by tests to start from a clean, freshly seeded store."""
    global _memory_repo
    from .demo import seed
    _memory_repo = InMemoryRepository()
    seed(_memory_repo)
    return _memory_repo


@lru_cache
def _admin_client(url: str, service_key: str):
    from supabase import create_client
    return create_client(url, service_key)


def _user_client(settings: Settings, access_token: str):
    from supabase import create_client
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    # Every PostgREST call then runs as this user, so RLS applies.
    client.postgrest.auth(access_token)
    return client


@dataclass
class Session:
    user_id: str
    role: UserRole
    profile: ProfileRecord
    repo: Repository
    settings: Settings
    is_demo: bool

    @property
    def target_profile(self) -> TargetProfile:
        return self.profile.target_profile

    def require_reviewer(self) -> None:
        if self.role is not UserRole.REVIEWER:
            raise forbidden("هذه الصفحة مخصّصة للمراجعين المصرّح لهم فقط.")


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise unauthorized()
    token = authorization[7:].strip()
    if not token:
        raise unauthorized()
    return token


def get_session(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> Session:
    token = _bearer(authorization)

    if settings.effective_demo_mode:
        from .demo import DEMO_TOKENS
        user_id = DEMO_TOKENS.get(token)
        if user_id is None:
            raise unauthorized("رمز الدخول التجريبي غير صالح.")
        repo = memory_repo()
        profile = repo.get_profile(user_id)
        if profile is None:
            raise unauthorized()
        return Session(user_id, profile.role, profile, repo, settings, True)

    admin = _admin_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        auth_user = admin.auth.get_user(token)
    except Exception:
        raise unauthorized("انتهت صلاحية الجلسة. سجّل الدخول من جديد.") from None
    if auth_user is None or getattr(auth_user, "user", None) is None:
        raise unauthorized("انتهت صلاحية الجلسة. سجّل الدخول من جديد.")

    user_id = auth_user.user.id
    repo = SupabaseRepository(_user_client(settings, token), admin)
    profile = repo.get_profile(user_id)
    if profile is None:
        profile = repo.upsert_profile(ProfileRecord(
            id=user_id, pseudo_id=new_pseudo("SP"), role=UserRole.PATIENT,
            target_profile=TargetProfile.UNSPECIFIED,
            display_name=(auth_user.user.user_metadata or {}).get("display_name"),
            is_synthetic=False,
        ))
    request.state.user_id = user_id
    return Session(user_id, profile.role, profile, repo, settings, False)


def get_reviewer_session(session: Session = Depends(get_session)) -> Session:
    session.require_reviewer()
    return session


@lru_cache
def get_gemini(settings_key: str = "") -> GeminiService:  # pragma: no cover - wiring
    return GeminiService(get_settings())


def get_processor() -> ReportProcessor:
    return ReportProcessor(get_settings())
