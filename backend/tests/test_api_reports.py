"""Upload, processing, history, corrections and patient data isolation."""

from __future__ import annotations

from .conftest import make_image_only_pdf, make_pdf, upload


def test_health_and_config(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    cfg = client.get("/api/v1/config").json()
    assert cfg["demo_mode"] is True
    assert cfg["supabase_configured"] is False
    assert cfg["setup_notes_ar"], "an unconfigured server must say so explicitly"


def test_every_patient_route_requires_authentication(client):
    for path in ("/api/v1/me", "/api/v1/reports", "/api/v1/home",
                 "/api/v1/notifications", "/api/v1/appointments", "/api/v1/visit-prep"):
        assert client.get(path).status_code == 401, path


def test_rejects_an_invalid_token(client):
    r = client.get("/api/v1/me", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_upload_processes_the_report_end_to_end(client, patient_headers, report_pdf):
    r = upload(client, patient_headers, report_pdf)
    assert r.status_code == 202
    report_id = r.json()["report"]["id"]

    status = client.get(f"/api/v1/reports/{report_id}/status", headers=patient_headers).json()
    assert status["ready"] is True
    assert status["failed"] is False

    detail = client.get(f"/api/v1/reports/{report_id}", headers=patient_headers).json()
    assert detail["format_id"] == "omnipod_discover_agp_summary_v1"
    assert detail["page_count"] >= 1
    assert detail["data_quality"]["days_of_data"] == 14
    assert detail["data_quality"]["coverage_percent"] == 88
    assert detail["data_quality"]["sufficient"] is True
    assert detail["analysis"]["outcome"] in (
        "routine_summary", "review_suggested", "need_more_data")


def test_extracted_values_are_traceable_to_the_source(client, patient_headers, report_pdf):
    report_id = upload(client, patient_headers, report_pdf).json()["report"]["id"]
    metrics = client.get(f"/api/v1/reports/{report_id}/metrics", headers=patient_headers).json()
    extracted = [f for f in metrics["extraction"]["fields"] if f["extracted_value"] is not None]
    assert extracted
    for f in extracted:
        assert f["source_label"]
        assert f["source_page"] == 1
        assert f["source_text"]


def test_derived_metrics_are_labelled_as_derived(client, patient_headers, report_pdf):
    report_id = upload(client, patient_headers, report_pdf).json()["report"]["id"]
    metrics = client.get(f"/api/v1/reports/{report_id}/metrics", headers=patient_headers).json()
    by_key = {m["key"]: m for m in metrics["metrics"]}
    # the fixture prints TBR/TAR, so they stay "extracted"
    assert by_key["time_below_range_total"]["origin"] == "extracted_from_report"
    assert by_key["mean_glucose"]["status"] == "verified"


def test_report_with_no_glucose_metrics_fails_with_an_arabic_reason(client, patient_headers):
    pdf = make_pdf(["Invoice 2026", "Total due 350 SAR", "Thank you"])
    report_id = upload(client, patient_headers, pdf).json()["report"]["id"]
    status = client.get(f"/api/v1/reports/{report_id}/status", headers=patient_headers).json()
    assert status["failed"] is True
    assert "مؤشر سكر" in status["error_ar"]


def test_scanned_report_is_rejected_with_an_ocr_explanation(client, patient_headers):
    report_id = upload(client, patient_headers, make_image_only_pdf()).json()["report"]["id"]
    status = client.get(f"/api/v1/reports/{report_id}/status", headers=patient_headers).json()
    assert status["failed"] is True
    assert "OCR" in status["error_ar"]


def test_rejects_a_non_pdf_upload(client, patient_headers):
    r = upload(client, patient_headers, b"just text, not a pdf", name="notes.txt")
    assert r.status_code == 422
    assert "PDF" in r.json()["detail"]["message_ar"]


def test_rejects_a_truncated_pdf(client, patient_headers):
    r = upload(client, patient_headers, b"%PDF-1.7 broken")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "truncated"


def test_rejects_an_oversized_upload(client, patient_headers, monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_bytes", 100, raising=False)
    r = upload(client, patient_headers, b"%PDF-1.7" + b"x" * 500 + b"%%EOF")
    assert r.status_code == 413


def test_history_lists_the_uploaded_reports(client, patient_headers, report_pdf):
    upload(client, patient_headers, report_pdf)
    upload(client, patient_headers, report_pdf)
    body = client.get("/api/v1/reports", headers=patient_headers).json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


def test_a_patient_cannot_read_another_users_report(client, patient_headers, reviewer_headers, report_pdf):
    report_id = upload(client, patient_headers, report_pdf).json()["report"]["id"]
    r = client.get(f"/api/v1/reports/{report_id}", headers=reviewer_headers)
    assert r.status_code == 404


def test_correcting_a_value_reruns_the_checks_and_the_analysis(client, patient_headers, report_pdf):
    report_id = upload(client, patient_headers, report_pdf).json()["report"]["id"]
    r = client.patch(
        f"/api/v1/reports/{report_id}/fields", headers=patient_headers,
        json={"updates": [{"metric_key": "time_very_low", "corrected_value": 9.0}]},
    )
    assert r.status_code == 200
    detail = r.json()
    band_sum = next(c for c in detail["extraction"]["checks"] if c["id"] == "band_sum")
    assert band_sum["passed"] is False  # the five bands no longer total 100 %
    field = next(f for f in detail["extraction"]["fields"] if f["key"] == "time_very_low")
    assert field["corrected_value"] == 9.0
    assert field["extracted_value"] == 1.4  # the original is preserved
    assert detail["status"] == "needs_review"


def test_marking_a_value_unavailable_never_stores_zero(client, patient_headers, report_pdf):
    report_id = upload(client, patient_headers, report_pdf).json()["report"]["id"]
    r = client.patch(
        f"/api/v1/reports/{report_id}/fields", headers=patient_headers,
        json={"updates": [{"metric_key": "cv", "mark_unavailable": True}]},
    )
    metrics = {m["key"]: m for m in r.json()["verified_metrics"]}
    assert metrics["cv"]["value"] is None
    assert metrics["cv"]["status"] == "unavailable"


def test_unknown_metric_key_is_rejected(client, patient_headers, report_pdf):
    report_id = upload(client, patient_headers, report_pdf).json()["report"]["id"]
    r = client.patch(
        f"/api/v1/reports/{report_id}/fields", headers=patient_headers,
        json={"updates": [{"metric_key": "blood_pressure", "corrected_value": 1}]},
    )
    assert r.status_code == 400


def test_summary_falls_back_to_a_local_template_without_gemini(client, patient_headers, report_pdf):
    report_id = upload(client, patient_headers, report_pdf).json()["report"]["id"]
    summary = client.get(f"/api/v1/reports/{report_id}/summary", headers=patient_headers).json()
    assert summary["ai_summary"]["source"] == "local_template"
    assert summary["ai_summary"]["fallback_reason_ar"]
    assert "القيم الموثّقة" in summary["ai_summary"]["text"]
