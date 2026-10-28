"""The data behind the four main screens and the Sukkar Plus landing screen."""

from __future__ import annotations

from .conftest import upload


def test_profile_screen_exposes_the_sukkar_plus_service_state(client, patient_headers):
    body = client.get("/api/v1/me/health-profile", headers=patient_headers).json()
    assert body["profile"]["display_name"]
    assert body["profile"]["is_synthetic"] is True
    assert body["sukkar_plus"]["reports_count"] == 0
    assert body["sukkar_plus"]["latest_report"] is None
    assert body["targets"]["items"], "the selected target profile must expose its reference targets"


def test_home_reflects_the_real_journey_state(client, patient_headers, report_pdf):
    home = client.get("/api/v1/home", headers=patient_headers).json()
    assert home["sukkar_plus"]["state"] == "no_report"
    assert home["demo_mode"] is True

    upload(client, patient_headers, report_pdf)
    home = client.get("/api/v1/home", headers=patient_headers).json()
    assert home["sukkar_plus"]["state"] == "ready"
    assert home["sukkar_plus"]["reports_count"] == 1
    assert home["unread_notifications"] >= 1


def test_sukkar_state_has_no_fabricated_metrics_before_an_upload(client, patient_headers):
    state = client.get("/api/v1/sukkar/state", headers=patient_headers).json()
    assert state["journey"]["state"] == "no_report"
    assert state["recent_reports"] == []
    assert state["reports_total"] == 0
    assert len(state["how_it_works"]) == 5
    assert any("صحتي" in s for s in state["limits_ar"])


def test_journey_advances_through_the_whole_workflow(
        client, patient_headers, reviewer_headers, report_pdf):
    report_id = upload(client, patient_headers, report_pdf).json()["report"]["id"]
    f = client.post("/api/v1/followups", headers=patient_headers, json={
        "report_id": report_id, "reason_ar": "أرغب في مراجعة تقريري."}).json()

    state = client.get("/api/v1/sukkar/state", headers=patient_headers).json()
    assert state["journey"]["state"] == "followup_pending"

    client.post(f"/api/v1/reviewer/requests/{f['id']}/start", headers=reviewer_headers)
    client.post(f"/api/v1/reviewer/requests/{f['id']}/decide", headers=reviewer_headers,
                json={"decision": "review_required"})

    state = client.get("/api/v1/sukkar/state", headers=patient_headers).json()
    assert state["journey"]["state"] == "appointment_ready"
    assert all(step["done"] for step in state["journey"]["steps"])


def test_appointments_are_always_labelled_as_a_prototype(client, patient_headers):
    body = client.get("/api/v1/appointments", headers=patient_headers).json()
    assert "لم يُحجز أي موعد حقيقي" in body["prototype_note_ar"]
    assert all(a["is_simulated"] for a in body["past"])


def test_wellness_content_is_general_and_carries_sources(client, patient_headers):
    body = client.get("/api/v1/wellness", headers=patient_headers).json()
    assert len(body["topics"]) >= 5
    assert any(t["source_ref"] for t in body["topics"])
    assert "لا يتضمن تشخيصًا" in body["disclaimer_ar"]
    text = " ".join(" ".join(t["body_ar"]) for t in body["topics"])
    assert "جرعة" not in text and "وحدة إنسولين" not in text


def test_target_profile_can_be_changed_and_changes_the_analysis(client, patient_headers):
    r = client.patch("/api/v1/me/target-profile", headers=patient_headers,
                     json={"target_profile": "older_or_high_risk"})
    assert r.json()["profile"]["target_profile"] == "older_or_high_risk"
    body = client.get("/api/v1/me/health-profile", headers=patient_headers).json()
    tir = next(i for i in body["targets"]["items"] if i["metric"] == "time_in_range")
    assert "50" in tir["text_ar"]
