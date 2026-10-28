"""Runtime configuration. Secrets come from environment variables only."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from pydantic import Field

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Supabase -------------------------------------------------------
    supabase_url: str = ""
    supabase_anon_key: str = ""
    # Server-side only. Never returned to the browser.
    supabase_service_role_key: str = ""
    supabase_reports_bucket: str = "reports"

    # --- Gemini ---------------------------------------------------------
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = 45.0
    ai_provider: Literal["deepseek", "gemini", "local"] = "deepseek"
    deepseek_api_key: str = Field(default="", repr=False)
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout_seconds: float = 90.0

    # --- App ------------------------------------------------------------
    environment: str = "demo"          # "demo" | "live"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_bytes: int = 15 * 1024 * 1024
    # When true the API serves a seeded, clearly-labelled synthetic dataset
    # in memory. Forced on when Supabase is not configured.
    demo_mode: bool = True
    # Keep uploaded PDFs in Supabase Storage (private bucket + signed URLs).
    store_report_files: bool = True
    report_retention_days: int = 180

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key and self.supabase_service_role_key)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def deepseek_configured(self) -> bool:
        return bool(self.deepseek_api_key.strip())

    @property
    def effective_demo_mode(self) -> bool:
        return self.demo_mode or not self.supabase_configured

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
