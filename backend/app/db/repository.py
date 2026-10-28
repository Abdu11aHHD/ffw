"""Data access. Two interchangeable implementations behind one protocol.

* InMemoryRepository - demo mode and tests. Clearly labelled synthetic data.
* SupabaseRepository - live mode. Patient reads/writes go through PostgREST
  with the caller's own JWT so Row Level Security applies; privileged
  operations (simulated appointment creation, notifications, reviewer
  queues, private storage) use the service-role client on the server only.
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from threading import RLock
from datetime import datetime, timedelta, timezone
from typing import Protocol

from ..domain.followup import (
    FollowUpRequest,
    DuplicateRequestError,
    FollowUpStatus,
    FollowUpTrigger,
    ReviewDecision,
    ReviewNote,
    SharedSnapshot,
    StatusHistoryEntry,
)
from ..domain.metrics import DataProvenance, TargetProfile, UserRole
from .models import (
    AppointmentRecord,
    NotificationRecord,
    NotificationKind,
    ProfileRecord,
    ReportRecord,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


def new_pseudo(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


class ReviewConflictError(Exception):
    """The stored request changed after the reviewer loaded it."""


class Repository(Protocol):
    is_demo: bool
    def store_report_file(self, r: ReportRecord, data: bytes, bucket: str) -> str: ...
    def signed_report_url(self, path: str, bucket: str) -> str: ...
    def commit_review(self, f: FollowUpRequest, expected_at: datetime, appointment: AppointmentRecord | None, notifications: list[NotificationRecord]) -> None: ...

    # profiles
    def get_profile(self, user_id: str) -> ProfileRecord | None: ...
    def upsert_profile(self, p: ProfileRecord) -> ProfileRecord: ...
    def set_target_profile(self, user_id: str, profile: TargetProfile) -> ProfileRecord: ...

    # reports
    def create_report(self, r: ReportRecord) -> ReportRecord: ...
    def save_report(self, r: ReportRecord) -> ReportRecord: ...
    def get_report(self, user_id: str, report_id: str) -> ReportRecord | None: ...
    def get_report_any(self, report_id: str) -> ReportRecord | None: ...
    def list_reports(self, user_id: str, limit: int = 50, offset: int = 0) -> tuple[list[ReportRecord], int]: ...

    # follow-ups
    def create_followup(self, f: FollowUpRequest) -> FollowUpRequest: ...
    def save_followup(self, f: FollowUpRequest) -> FollowUpRequest: ...
    def get_followup(self, request_id: str) -> FollowUpRequest | None: ...
    def list_followups(self, user_id: str) -> list[FollowUpRequest]: ...
    def list_reviewer_queue(self, statuses: list[str], limit: int, offset: int) -> tuple[list[FollowUpRequest], int]: ...

    # appointments
    def create_appointment(self, a: AppointmentRecord) -> AppointmentRecord: ...
    def list_appointments(self, user_id: str) -> list[AppointmentRecord]: ...
    def get_appointment(self, user_id: str, appointment_id: str) -> AppointmentRecord | None: ...
    def appointment_for_followup(self, followup_id: str) -> AppointmentRecord | None: ...

    # notifications
    def create_notification(self, n: NotificationRecord) -> NotificationRecord | None: ...
    def list_notifications(self, user_id: str, channel: str | None = None) -> list[NotificationRecord]: ...
    def get_notification(self, user_id: str, notification_id: str) -> NotificationRecord | None: ...
    def mark_notification_read(self, user_id: str, notification_id: str) -> NotificationRecord | None: ...
    def mark_all_notifications_read(self, user_id: str) -> int: ...
    def delete_all_notifications(self, user_id: str, channel: str | None = None) -> int: ...


# =====================================================================
# In-memory
# =====================================================================


class InMemoryRepository:
    """Process-local store used in demo mode and in tests."""

    is_demo = True

    def __init__(self) -> None:
        self._lock = RLock()
        self.profiles: dict[str, ProfileRecord] = {}
        self.reports: dict[str, ReportRecord] = {}
        self.followups: dict[str, FollowUpRequest] = {}
        self.appointments: dict[str, AppointmentRecord] = {}
        self.notifications: dict[str, NotificationRecord] = {}
        self._dedupe: set[tuple[str, str]] = set()

    # ---- profiles
    def get_profile(self, user_id: str) -> ProfileRecord | None:
        return self.profiles.get(user_id)

    def upsert_profile(self, p: ProfileRecord) -> ProfileRecord:
        self.profiles[p.id] = p
        return p

    def set_target_profile(self, user_id: str, profile: TargetProfile) -> ProfileRecord:
        p = self.profiles[user_id]
        p.target_profile = profile
        return p

    # ---- reports
    def create_report(self, r: ReportRecord) -> ReportRecord:
        self.reports[r.id] = deepcopy(r)
        return r

    def save_report(self, r: ReportRecord) -> ReportRecord:
        self.reports[r.id] = deepcopy(r)
        return r

    def get_report(self, user_id: str, report_id: str) -> ReportRecord | None:
        r = self.reports.get(report_id)
        return deepcopy(r) if (r and r.user_id == user_id) else None

    def get_report_any(self, report_id: str) -> ReportRecord | None:
        return deepcopy(self.reports.get(report_id))

    def list_reports(self, user_id: str, limit: int = 50, offset: int = 0) -> tuple[list[ReportRecord], int]:
        rows = sorted((r for r in self.reports.values() if r.user_id == user_id),
                      key=lambda r: r.created_at, reverse=True)
        return deepcopy(rows[offset:offset + limit]), len(rows)

    # ---- follow-ups
    def create_followup(self, f: FollowUpRequest) -> FollowUpRequest:
        with self._lock:
            for existing in self.followups.values():
                if existing.idempotency_key == f.idempotency_key and existing.status.is_open:
                    raise DuplicateRequestError(existing.id)
            self.followups[f.id] = deepcopy(f)
        return f

    def save_followup(self, f: FollowUpRequest) -> FollowUpRequest:
        with self._lock:
            self.followups[f.id] = deepcopy(f)
        return f

    def get_followup(self, request_id: str) -> FollowUpRequest | None:
        return deepcopy(self.followups.get(request_id))

    def commit_review(self, f: FollowUpRequest, expected_at: datetime,
                      appointment: AppointmentRecord | None, notifications: list[NotificationRecord]) -> None:
        with self._lock:
            current = self.followups.get(f.id)
            if current is None or current.status is not FollowUpStatus.UNDER_REVIEW or current.updated_at != expected_at:
                raise ReviewConflictError()
            self.followups[f.id] = deepcopy(f)
            if appointment is not None:
                self.appointments[appointment.id] = appointment
            for n in notifications:
                self.create_notification(n)

    def list_followups(self, user_id: str) -> list[FollowUpRequest]:
        return sorted((f for f in self.followups.values() if f.user_id == user_id),
                      key=lambda f: f.created_at, reverse=True)

    def list_reviewer_queue(self, statuses: list[str], limit: int, offset: int) -> tuple[list[FollowUpRequest], int]:
        rows = sorted(
            (f for f in self.followups.values()
             if f.status is not FollowUpStatus.DRAFT and f.status.value in statuses),
            key=lambda f: f.updated_at, reverse=True)
        return rows[offset:offset + limit], len(rows)

    # ---- appointments
    def create_appointment(self, a: AppointmentRecord) -> AppointmentRecord:
        self.appointments[a.id] = a
        return a

    def list_appointments(self, user_id: str) -> list[AppointmentRecord]:
        return sorted((a for a in self.appointments.values() if a.user_id == user_id),
                      key=lambda a: a.scheduled_at)

    def get_appointment(self, user_id: str, appointment_id: str) -> AppointmentRecord | None:
        a = self.appointments.get(appointment_id)
        return a if (a and a.user_id == user_id) else None

    def appointment_for_followup(self, followup_id: str) -> AppointmentRecord | None:
        return next((a for a in self.appointments.values() if a.followup_id == followup_id), None)

    # ---- notifications
    def create_notification(self, n: NotificationRecord) -> NotificationRecord | None:
        if n.dedupe_key:
            key = (n.user_id, n.dedupe_key)
            if key in self._dedupe:
                return None
            self._dedupe.add(key)
        self.notifications[n.id] = n
        return n

    def list_notifications(self, user_id: str, channel: str | None = None) -> list[NotificationRecord]:
        return sorted(
            (n for n in self.notifications.values()
             if n.user_id == user_id and (channel is None or n.channel == channel)),
            key=lambda n: n.created_at, reverse=True)

    def get_notification(self, user_id: str, notification_id: str) -> NotificationRecord | None:
        n = self.notifications.get(notification_id)
        return n if (n and n.user_id == user_id) else None

    def mark_notification_read(self, user_id: str, notification_id: str) -> NotificationRecord | None:
        n = self.get_notification(user_id, notification_id)
        if n and n.read_at is None:
            n.read_at = now_utc()
        return n

    def mark_all_notifications_read(self, user_id: str) -> int:
        count = 0
        for n in self.notifications.values():
            if n.user_id == user_id and n.read_at is None:
                n.read_at = now_utc()
                count += 1
        return count

    def delete_all_notifications(self, user_id: str, channel: str | None = None) -> int:
        ids = [k for k, n in self.notifications.items()
               if n.user_id == user_id and (channel is None or n.channel == channel)]
        for k in ids:
            self.notifications.pop(k, None)
        return len(ids)


# =====================================================================
# Supabase
# =====================================================================


def _dt(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class SupabaseRepository:
    """Live implementation.

    `user_client` carries the caller's JWT so every patient read/write is
    additionally constrained by Row Level Security. `admin_client` uses the
    service-role key and is used only where the prototype legitimately acts
    on the user's behalf: writing simulated appointments and notifications,
    serving the reviewer queue and signing private storage URLs.
    """

    is_demo = False

    def __init__(self, user_client, admin_client) -> None:
        self.db = user_client
        self.admin = admin_client

    def store_report_file(self, r: ReportRecord, data: bytes, bucket: str) -> str:
        path = f"{r.user_id}/{r.id}.pdf"
        self.admin.storage.from_(bucket).upload(path, data, {"content-type": "application/pdf", "upsert": "false"})
        return path

    def signed_report_url(self, path: str, bucket: str) -> str:
        result = self.admin.storage.from_(bucket).create_signed_url(path, 300)
        return result["signedURL"]

    # ---- profiles
    def get_profile(self, user_id: str) -> ProfileRecord | None:
        res = self.db.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if not res.data:
            return None
        row = res.data[0]
        ident = self.db.table("patient_identities").select("display_name, health_record_number") \
            .eq("user_id", user_id).limit(1).execute()
        name = ident.data[0]["display_name"] if ident.data else None
        hrn = ident.data[0].get("health_record_number") if ident.data else None
        return ProfileRecord(
            id=row["id"], pseudo_id=row["pseudo_id"], role=UserRole(row["role"]),
            target_profile=TargetProfile(row["target_profile"]),
            display_name=name, health_record_number=hrn, is_synthetic=False,
        )

    def upsert_profile(self, p: ProfileRecord) -> ProfileRecord:
        self.admin.table("profiles").upsert({
            "id": p.id, "pseudo_id": p.pseudo_id, "role": p.role.value,
            "target_profile": p.target_profile.value,
        }).execute()
        if p.display_name or p.health_record_number:
            self.admin.table("patient_identities").upsert({
                "user_id": p.id, "display_name": p.display_name,
                "health_record_number": p.health_record_number,
            }).execute()
        return p

    def set_target_profile(self, user_id: str, profile: TargetProfile) -> ProfileRecord:
        self.db.table("profiles").update({"target_profile": profile.value}).eq("id", user_id).execute()
        return self.get_profile(user_id)

    # ---- reports
    @staticmethod
    def _report_row(r: ReportRecord) -> dict:
        return {
            "id": r.id, "user_id": r.user_id, "status": r.status,
            "created_at": r.created_at.isoformat(), "file_name": r.file_name,
            "file_size_bytes": r.file_size_bytes, "file_sha256": r.file_sha256,
            "page_count": r.page_count, "storage_path": r.storage_path,
            "format_id": r.format_id, "format_verified": r.format_verified,
            "device_label": r.device_label, "glucose_unit": r.glucose_unit,
            "report_period": r.report_period, "metrics_period": r.metrics_period,
            "data_quality": r.data_quality, "warnings": r.warnings_ar,
            "extraction": r.extraction, "verified_metrics": r.verified_metrics,
            "analysis": r.analysis, "ai_summary": r.ai_summary,
            "error_ar": r.error_ar, "provenance": r.provenance,
        }

    @staticmethod
    def _report_from_row(row: dict) -> ReportRecord:
        return ReportRecord(
            id=row["id"], user_id=row["user_id"], status=row["status"],
            created_at=_dt(row["created_at"]), file_name=row.get("file_name") or "",
            file_size_bytes=row.get("file_size_bytes") or 0,
            file_sha256=row.get("file_sha256"), page_count=row.get("page_count") or 0,
            storage_path=row.get("storage_path"), format_id=row.get("format_id"),
            format_verified=bool(row.get("format_verified")),
            device_label=row.get("device_label"),
            glucose_unit=row.get("glucose_unit") or "mg/dL",
            report_period=row.get("report_period"), metrics_period=row.get("metrics_period"),
            data_quality=row.get("data_quality"), warnings_ar=list(row.get("warnings") or []),
            extraction=row.get("extraction"), verified_metrics=list(row.get("verified_metrics") or []),
            analysis=row.get("analysis"), ai_summary=row.get("ai_summary"),
            error_ar=row.get("error_ar"), provenance=row.get("provenance") or "real",
        )

    def create_report(self, r: ReportRecord) -> ReportRecord:
        self.db.table("sukkar_reports").insert(self._report_row(r)).execute()
        return r

    def save_report(self, r: ReportRecord) -> ReportRecord:
        # Background processing runs outside a request context, so it writes
        # with the service-role client; ownership is already fixed on the row.
        self.admin.table("sukkar_reports").update(self._report_row(r)).eq("id", r.id).execute()
        return r

    def get_report(self, user_id: str, report_id: str) -> ReportRecord | None:
        res = self.db.table("sukkar_reports").select("*").eq("id", report_id).limit(1).execute()
        if not res.data:
            return None
        row = res.data[0]
        return self._report_from_row(row) if row["user_id"] == user_id else None

    def get_report_any(self, report_id: str) -> ReportRecord | None:
        res = self.admin.table("sukkar_reports").select("*").eq("id", report_id).limit(1).execute()
        return self._report_from_row(res.data[0]) if res.data else None

    def list_reports(self, user_id: str, limit: int = 50, offset: int = 0) -> tuple[list[ReportRecord], int]:
        res = (self.db.table("sukkar_reports").select("*", count="exact")
               .eq("user_id", user_id).order("created_at", desc=True)
               .range(offset, offset + limit - 1).execute())
        return [self._report_from_row(r) for r in (res.data or [])], (res.count or 0)

    # ---- follow-ups
    @staticmethod
    def _followup_row(f: FollowUpRequest) -> dict:
        return {
            "id": f.id, "pseudo_ref": f.pseudo_ref, "user_id": f.user_id,
            "report_id": f.report_id, "trigger_type": f.trigger.value,
            "rule_ids": list(f.rule_ids), "rules_version": f.rules_version,
            "reason": f.reason_ar, "shared_snapshot": f.snapshot.to_json(),
            "status": f.status.value, "decision": f.decision.value if f.decision else None,
            "idempotency_key": f.idempotency_key, "provenance": f.provenance.value,
            "created_at": f.created_at.isoformat(), "updated_at": f.updated_at.isoformat(),
            "appointment_id": f.appointment_id,
        }

    def _followup_from_row(self, row: dict, with_children: bool = True) -> FollowUpRequest:
        f = FollowUpRequest(
            id=row["id"], pseudo_ref=row["pseudo_ref"], user_id=row.get("user_id") or "",
            trigger=FollowUpTrigger(row["trigger_type"]), rule_ids=list(row.get("rule_ids") or []),
            rules_version=row["rules_version"], reason_ar=row["reason"],
            snapshot=SharedSnapshot.from_json(row.get("shared_snapshot") or {}),
            status=FollowUpStatus(row["status"]), idempotency_key=row.get("idempotency_key") or "",
            created_at=_dt(row["created_at"]), updated_at=_dt(row["updated_at"]),
            provenance=DataProvenance(row.get("provenance") or "real"),
            report_id=row.get("report_id"),
            decision=ReviewDecision(row["decision"]) if row.get("decision") else None,
            appointment_id=row.get("appointment_id"),
        )
        if with_children:
            h = (self.db.table("followup_status_history").select("*")
                 .eq("request_id", f.id).order("created_at").execute())
            f.history = [
                StatusHistoryEntry(
                    FollowUpStatus(r["from_status"]) if r.get("from_status") else None,
                    FollowUpStatus(r["to_status"]), _dt(r["created_at"]),
                    UserRole(r["actor_role"]) if r["actor_role"] in ("patient", "reviewer") else UserRole.PATIENT,
                    r.get("note"),
                ) for r in (h.data or [])
            ]
            n = (self.db.table("review_notes").select("*")
                 .eq("request_id", f.id).order("created_at").execute())
            f.notes = [ReviewNote(_dt(r["created_at"]), r["body"], r["author_label"]) for r in (n.data or [])]
        return f

    def create_followup(self, f: FollowUpRequest) -> FollowUpRequest:
        try:
            self.admin.table("followup_requests").insert(self._followup_row(f)).execute()
        except Exception as exc:
            if "23505" in str(exc) or "duplicate key" in str(exc).lower():
                raise DuplicateRequestError(f.id) from None
            raise
        self._write_history(f)
        return f

    def _write_history(self, f: FollowUpRequest) -> None:
        if not f.history:
            return
        last = f.history[-1]
        self.admin.table("followup_status_history").insert({
            "request_id": f.id,
            "from_status": last.from_status.value if last.from_status else None,
            "to_status": last.to_status.value,
            "actor_role": last.actor_role.value,
            "note": last.note_ar,
            "created_at": last.at.isoformat(),
        }).execute()

    def commit_review(self, f: FollowUpRequest, expected_at: datetime,
                      appointment: AppointmentRecord | None, notifications: list[NotificationRecord]) -> None:
        a = appointment
        appt = None if a is None else {
            "id": a.id, "user_id": a.user_id, "scheduled_at": a.scheduled_at.isoformat(),
            "clinic_label": a.clinic_label, "specialty_ar": a.specialty_ar,
            "followup_id": f.id, "report_id": a.report_id, "provenance": a.provenance,
        }
        h = f.history[-1]
        note = f.notes[-1] if f.notes and f.notes[-1].at == f.updated_at else None
        try:
            self.admin.rpc("adheed_commit_review", {
                "p_request": self._followup_row(f), "p_expected_at": expected_at.isoformat(),
                "p_history": {"from_status": h.from_status.value, "to_status": h.to_status.value,
                              "actor_role": h.actor_role.value, "note": h.note_ar, "created_at": h.at.isoformat()},
                "p_note": None if note is None else {"body": note.text_ar, "author_label": note.author_label},
                "p_appointment": appt,
                "p_notifications": [{"id": n.id, "kind": n.kind, "channel": n.channel,
                    "title": n.title_ar, "body": n.body_ar, "sender": n.sender_ar,
                    "dedupe_key": n.dedupe_key, "link": n.link, "created_at": n.created_at.isoformat()}
                    for n in notifications],
            }).execute()
        except Exception as exc:
            if "ADHEED_CONFLICT" in str(exc):
                raise ReviewConflictError() from None
            raise

    def save_followup(self, f: FollowUpRequest) -> FollowUpRequest:
        self.admin.table("followup_requests").update(self._followup_row(f)).eq("id", f.id).execute()
        self._write_history(f)
        if f.notes:
            note = f.notes[-1]
            existing = (self.admin.table("review_notes").select("id")
                        .eq("request_id", f.id).eq("created_at", note.at.isoformat()).execute())
            if not existing.data:
                self.admin.table("review_notes").insert({
                    "request_id": f.id, "author_label": note.author_label,
                    "body": note.text_ar, "created_at": note.at.isoformat(),
                }).execute()
        return f

    def get_followup(self, request_id: str) -> FollowUpRequest | None:
        res = self.admin.table("followup_requests").select("*").eq("id", request_id).limit(1).execute()
        return self._followup_from_row(res.data[0]) if res.data else None

    def list_followups(self, user_id: str) -> list[FollowUpRequest]:
        res = (self.db.table("followup_requests").select("*")
               .eq("user_id", user_id).order("created_at", desc=True).execute())
        return [self._followup_from_row(r, with_children=False) for r in (res.data or [])]

    def list_reviewer_queue(self, statuses: list[str], limit: int, offset: int) -> tuple[list[FollowUpRequest], int]:
        res = (self.admin.table("followup_requests").select("*", count="exact")
               .in_("status", statuses).neq("status", "draft")
               .order("updated_at", desc=True).range(offset, offset + limit - 1).execute())
        return [self._followup_from_row(r, with_children=False) for r in (res.data or [])], (res.count or 0)

    # ---- appointments
    def create_appointment(self, a: AppointmentRecord) -> AppointmentRecord:
        self.admin.table("appointments").insert({
            "id": a.id, "user_id": a.user_id, "scheduled_at": a.scheduled_at.isoformat(),
            "clinic_label": a.clinic_label, "specialty_ar": a.specialty_ar,
            "is_simulated": True, "status": a.status, "source": a.source,
            "followup_id": a.followup_id, "report_id": a.report_id,
            "provenance": a.provenance,
        }).execute()
        return a

    @staticmethod
    def _appointment_from_row(row: dict) -> AppointmentRecord:
        return AppointmentRecord(
            id=row["id"], user_id=row["user_id"], scheduled_at=_dt(row["scheduled_at"]),
            clinic_label=row["clinic_label"], specialty_ar=row.get("specialty_ar") or "",
            is_simulated=bool(row.get("is_simulated", True)), status=row.get("status") or "upcoming",
            source=row.get("source") or "prototype", followup_id=row.get("followup_id"),
            report_id=row.get("report_id"), provenance=row.get("provenance") or "synthetic",
        )

    def list_appointments(self, user_id: str) -> list[AppointmentRecord]:
        res = (self.db.table("appointments").select("*")
               .eq("user_id", user_id).order("scheduled_at").execute())
        return [self._appointment_from_row(r) for r in (res.data or [])]

    def get_appointment(self, user_id: str, appointment_id: str) -> AppointmentRecord | None:
        res = self.db.table("appointments").select("*").eq("id", appointment_id).limit(1).execute()
        if not res.data or res.data[0]["user_id"] != user_id:
            return None
        return self._appointment_from_row(res.data[0])

    def appointment_for_followup(self, followup_id: str) -> AppointmentRecord | None:
        res = (self.admin.table("appointments").select("*")
               .eq("followup_id", followup_id).limit(1).execute())
        return self._appointment_from_row(res.data[0]) if res.data else None

    # ---- notifications
    def create_notification(self, n: NotificationRecord) -> NotificationRecord | None:
        row = {
            "id": n.id, "user_id": n.user_id, "kind": n.kind, "channel": n.channel,
            "title": n.title_ar, "body": n.body_ar, "sender": n.sender_ar,
            "dedupe_key": n.dedupe_key, "link": n.link,
            "created_at": n.created_at.isoformat(),
        }
        try:
            self.admin.table("notifications").insert(row).execute()
        except Exception as exc:  # unique violation on (user_id, dedupe_key)
            if "duplicate key" in str(exc).lower() or "23505" in str(exc):
                return None
            raise
        return n

    @staticmethod
    def _notification_from_row(row: dict) -> NotificationRecord:
        return NotificationRecord(
            id=row["id"], user_id=row["user_id"], kind=row["kind"], channel=row["channel"],
            title_ar=row["title"], body_ar=row["body"], sender_ar=row.get("sender") or "سكر بلس",
            created_at=_dt(row["created_at"]),
            read_at=_dt(row["read_at"]) if row.get("read_at") else None,
            dedupe_key=row.get("dedupe_key"), link=row.get("link"),
        )

    def list_notifications(self, user_id: str, channel: str | None = None) -> list[NotificationRecord]:
        q = self.db.table("notifications").select("*").eq("user_id", user_id)
        if channel:
            q = q.eq("channel", channel)
        res = q.order("created_at", desc=True).execute()
        return [self._notification_from_row(r) for r in (res.data or [])]

    def get_notification(self, user_id: str, notification_id: str) -> NotificationRecord | None:
        res = self.db.table("notifications").select("*").eq("id", notification_id).limit(1).execute()
        if not res.data or res.data[0]["user_id"] != user_id:
            return None
        return self._notification_from_row(res.data[0])

    def mark_notification_read(self, user_id: str, notification_id: str) -> NotificationRecord | None:
        n = self.get_notification(user_id, notification_id)
        if n is None:
            return None
        if n.read_at is None:
            ts = now_utc()
            self.db.table("notifications").update({"read_at": ts.isoformat()}).eq("id", notification_id).execute()
            n.read_at = ts
        return n

    def mark_all_notifications_read(self, user_id: str) -> int:
        res = (self.db.table("notifications").update({"read_at": now_utc().isoformat()})
               .eq("user_id", user_id).is_("read_at", "null").execute())
        return len(res.data or [])

    def delete_all_notifications(self, user_id: str, channel: str | None = None) -> int:
        q = self.db.table("notifications").delete().eq("user_id", user_id)
        if channel:
            q = q.eq("channel", channel)
        res = q.execute()
        return len(res.data or [])
