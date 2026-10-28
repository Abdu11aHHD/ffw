from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("SUPABASE_URL", "")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ["AI_PROVIDER"] = "local"
os.environ["DEEPSEEK_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.demo import DEMO_PATIENT_TOKEN, DEMO_REVIEWER_TOKEN  # noqa: E402
from app.deps import reset_memory_repo  # noqa: E402
from app.main import create_app  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _clean_store():
    get_settings.cache_clear()
    reset_memory_repo()
    yield
    reset_memory_repo()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def patient_headers() -> dict:
    return {"Authorization": f"Bearer {DEMO_PATIENT_TOKEN}"}


@pytest.fixture
def reviewer_headers() -> dict:
    return {"Authorization": f"Bearer {DEMO_REVIEWER_TOKEN}"}


@pytest.fixture
def report_pdf() -> bytes:
    return (FIXTURES / "synthetic_discover_summary.pdf").read_bytes()


@pytest.fixture
def report_text() -> str:
    return (FIXTURES / "synthetic_discover_summary.pdfium.txt").read_text(encoding="utf-8")


def make_pdf(lines: list[str]) -> bytes:
    """Build a small text PDF in memory."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    y = 60
    for line in lines:
        page.insert_text((50, y), line, fontsize=11)
        y += 18
    data = doc.tobytes()
    doc.close()
    return data


def make_image_only_pdf() -> bytes:
    """A PDF with no extractable text, standing in for a scanned report."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.draw_rect(fitz.Rect(40, 40, 400, 300), color=(0, 0, 0), fill=(0.8, 0.8, 0.8))
    data = doc.tobytes()
    doc.close()
    return data


def upload(client, headers, data: bytes, name: str = "report.pdf"):
    return client.post(
        "/api/v1/reports", headers=headers,
        files={"file": (name, data, "application/pdf")},
    )
