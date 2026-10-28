"""Follow-up workflow, reviewer authorization, simulated appointments and notifications."""

from __future__ import annotations

import pytest

from .conftest import upload


@pytest.fixture
def ready_report(client, patient_headers, report_pdf) -> str:
    return upload(client, patient_headers, report_pdf).json()["report"]["id"]


def _create(client, headers, report_id, reason="أرغب في مراجعة تقريري قبل الموعد."):
    return client.post("/api/v1/followups", headers=headers,
                       json={"report_id": report_id, "reason_ar": reason})


# ------------------------------------------------------------- patient side


def test_patient_can_create_and_submit_a_follow_up(client, patient_headers, ready_report):
    r = _create(client, patient_headers, ready_report)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "awaiting_review"
    assert body["pseudo_ref"].startswith("REQ-")
    assert body["shared_snapshot"]["items"], "the reviewer snapshot must carry the shared metrics"


def test_duplicate_open_requests_are_prevented(client, patient_headers, ready_report):
    assert _create(client, patient_headers, ready_report).status_code == 201
    second = _create(client, patient_headers, ready_report)
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "duplicate_request"


def test_a_withdrawn_request_frees_the_idempotency_key(client, patient_headers, ready_report):
    first = _create(client, patient_headers, ready_report).json()
    client.post(f"/api/v1/followups/{first['id']}/withdraw", headers=patient_headers)
    assert _create(client, patient_headers, ready_report).status_code == 201


def test_a_submitted_request_cannot_be_submitted_again(client, patient_headers, ready_report):
    f = _create(client, patient_headers, ready_report).json()
    r = client.post(f"/api/v1/followups/{f['id']}/submit", headers=patient_headers)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_transition"


def test_a_request_under_review_cannot_be_withdrawn(client, patient_headers, reviewer_headers, ready_report):
    f = _create(client, patient_headers, ready_report).json()
    client.post(f"/api/v1/reviewer/requests/{f['id']}/start", headers=reviewer_headers)
    r = client.post(f"/api/v1/followups/{f['id']}/withdraw", headers=patient_headers)
    assert r.status_code == 400


# ------------------------------------------------------------ reviewer side


def test_a_patient_cannot_reach_the_reviewer_dashboard(client, patient_headers):
    assert client.get("/api/v1/reviewer/requests", headers=patient_headers).status_code == 403


def test_reviewer_endpoints_are_not_anonymous(client):
    assert client.get("/api/v1/reviewer/requests").status_code == 401


def test_reviewer_sees_submitted_requests_without_the_patient_identity(
        client, patient_headers, reviewer_headers, ready_report):
    _create(client, patient_headers, ready_report)
    queue = client.get("/api/v1/reviewer/requests", headers=reviewer_headers).json()
    assert queue["total"] == 1
    request_id = queue["items"][0]["id"]
    detail = client.get(f"/api/v1/reviewer/requests/{request_id}", headers=reviewer_headers).json()
    assert "user_id" not in detail
    assert detail["report"]["verified_metrics"]
    assert detail["report"]["analysis"]["outcome"]


def test_reviewer_never_sees_drafts(client, patient_headers, reviewer_headers, ready_report):
    draft = client.post("/api/v1/followups", headers=patient_headers, json={
        "report_id": ready_report, "reason_ar": "مسودة", "submit_now": False}).json()
    assert draft["status"] == "draft"
    queue = client.get("/api/v1/reviewer/requests", headers=reviewer_headers).json()
    assert queue["total"] == 0
    assert client.get(f"/api/v1/reviewer/requests/{draft['id']}",
                      headers=reviewer_headers).status_code == 404


def test_decision_requires_the_review_to_have_started(client, patient_headers, reviewer_headers, ready_report):
    f = _create(client, patient_headers, ready_report).json()
    r = client.post(f"/api/v1/reviewer/requests/{f['id']}/decide", headers=reviewer_headers,
                    json={"decision": "review_required"})
    assert r.status_code == 400


def test_approval_creates_exactly_one_simulated_appointment(
        client, patient_headers, reviewer_headers, ready_report):
    f = _create(client, patient_headers, ready_report).json()
    client.post(f"/api/v1/reviewer/requests/{f['id']}/start", headers=reviewer_headers)
    decided = client.post(
        f"/api/v1/reviewer/requests/{f['id']}/decide", headers=reviewer_headers,
        json={"decision": "review_required", "note_ar": "يستحق النقاش في الموعد القادم."}).json()

    assert decided["status"] == "reviewed"
    assert decided["appointment"]["is_simulated"] is True
    assert "تجريبي" in decided["appointment"]["simulated_label_ar"]

    appointments = client.get("/api/v1/appointments", headers=patient_headers).json()
    prototype = [a for a in appointments["upcoming"] if a["source"] == "prototype"]
    assert len(prototype) == 1
    assert all(a["is_simulated"] for a in appointments["upcoming"] + appointments["past"])


def test_rejection_creates_no_appointment(client, patient_headers, reviewer_headers, ready_report):
    f = _create(client, patient_headers, ready_report).json()
    client.post(f"/api/v1/reviewer/requests/{f['id']}/start", headers=reviewer_headers)
    client.post(f"/api/v1/reviewer/requests/{f['id']}/decide", headers=reviewer_headers,
                json={"decision": "data_completion", "note_ar": "نحتاج فترة أطول."})
    detail = client.get(f"/api/v1/followups/{f['id']}", headers=patient_headers).json()
    assert detail["status"] == "more_info_requested"
    assert detail["appointment"] is None
    upcoming = client.get("/api/v1/appointments", headers=patient_headers).json()["upcoming"]
    assert [a for a in upcoming if a["source"] == "prototype"] == []


def test_more_info_requested_can_be_resubmitted(client, patient_headers, reviewer_headers, ready_report):
    f = _create(client, patient_headers, ready_report).json()
    client.post(f"/api/v1/reviewer/requests/{f['id']}/start", headers=reviewer_headers)
    client.post(f"/api/v1/reviewer/requests/{f['id']}/decide", headers=reviewer_headers,
                json={"decision": "data_completion"})
    r = client.post(f"/api/v1/followups/{f['id']}/submit", headers=patient_headers)
    assert r.json()["status"] == "awaiting_review"


# --------------------------------------------------------- notifications


def test_notifications_come_from_real_events_and_never_duplicate(
        client, patient_headers, reviewer_headers, ready_report):
    before = client.get("/api/v1/notifications", headers=patient_headers).json()
    kinds = [n["kind"] for n in before["items"]]
    assert "report_ready" in kinds
    assert before["general_count"] == 2

    f = _create(client, patient_headers, ready_report).json()
    client.post(f"/api/v1/reviewer/requests/{f['id']}/start", headers=reviewer_headers)
    client.post(f"/api/v1/reviewer/requests/{f['id']}/decide", headers=reviewer_headers,
                json={"decision": "review_required"})

    after = client.get("/api/v1/notifications", headers=patient_headers).json()
    kinds = [n["kind"] for n in after["items"]]
    assert "followup_submitted" in kinds
    assert "followup_decided" in kinds
    assert "appointment_created" in kinds

    # reloading the list must not create anything new
    again = client.get("/api/v1/notifications", headers=patient_headers).json()
    assert len(again["items"]) == len(after["items"])


def test_mark_read_and_mark_all_read(client, patient_headers, ready_report):
    body = client.get("/api/v1/notifications", headers=patient_headers).json()
    first = body["items"][0]
    assert first["read"] is False
    read = client.post(f"/api/v1/notifications/{first['id']}/read", headers=patient_headers).json()
    assert read["read"] is True

    result = client.post("/api/v1/notifications/read-all", headers=patient_headers).json()
    assert result["count"] >= 1
    assert client.get("/api/v1/notifications", headers=patient_headers).json()["unread_total"] == 0


def test_notification_channels_are_separated(client, patient_headers):
    personal = client.get("/api/v1/notifications?channel=personal", headers=patient_headers).json()
    general = client.get("/api/v1/notifications?channel=general", headers=patient_headers).json()
    assert all(n["channel"] == "general" for n in general["items"])
    assert all(n["channel"] == "personal" for n in personal["items"])


def test_delete_all_clears_only_the_requested_channel(client, patient_headers, ready_report):
    client.delete("/api/v1/notifications?channel=general", headers=patient_headers)
    body = client.get("/api/v1/notifications", headers=patient_headers).json()
    assert body["general_count"] == 0
    assert body["personal_count"] >= 1


def test_a_patient_cannot_read_another_users_notification(client, patient_headers, reviewer_headers):
    mine = client.get("/api/v1/notifications", headers=patient_headers).json()["items"][0]
    r = client.get(f"/api/v1/notifications/{mine['id']}", headers=reviewer_headers)
    assert r.status_code == 404
