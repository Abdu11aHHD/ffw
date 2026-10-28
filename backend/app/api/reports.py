"""Report upload, processing status, history, details and corrections."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile

from ..db.models import ReportRecord, ReportStatus
from ..db.repository import new_id, now_utc
from ..deps import Session, get_processor, get_session
from ..domain.extraction import (
    NOT_FOUND_PERIOD,
    ExtractedField,
    ExtractedPeriod,
    ExtractionMethod,
    ExtractionResult,
    ExtractionStatus,
    FieldValidation,
    PdfValidationError,
    format_file_size,
    validate_pdf_bytes,
)
from ..domain.metrics import MetricKey, ReportPeriod
from ..domain.summary_checks import ConsistencyCheck
from ..domain.units import GlucoseUnit
from ..errors import bad_request, not_found, payload_too_large, unprocessable
from ..schemas.api import FieldUpdateBatch
from ..services.report_service import ReportProcessor, sha256_of

log = logging.getLogger("sukkar.api.reports")

router = APIRouter(prefix="/reports", tags=["reports"])


# --------------------------------------------------------------- helpers


def _rebuild_extraction(payload: dict) -> ExtractionResult:
    """Rehydrate an ExtractionResult from its stored JSON so corrections can
    re-run the same deterministic consistency checks."""
    fields: dict[MetricKey, ExtractedField] = {}
    for f in payload.get("fields", []):
        key = MetricKey(f["key"])
        fields[key] = ExtractedField(
            key=key,
            extracted_value=f.get("extracted_value"),
            unit=f.get("unit") or "%",
            extraction_status=ExtractionStatus(f["extraction_status"]),
            validation=FieldValidation(f["validation"]),
            method=ExtractionMethod(f["method"]),
            source_page=f.get("source_page"),
            source_label=f.get("source_label"),
            source_text=f.get("source_text"),
            messages_ar=list(f.get("messages_ar") or []),
            ai_value=f.get("ai_value"),
            corrected_value=f.get("corrected_value"),
            marked_unavailable=bool(f.get("marked_unavailable")),
            confirmed=bool(f.get("confirmed")),
        )

    def period(d: dict | None) -> ExtractedPeriod:
        if not d:
            return NOT_FOUND_PERIOD
        from datetime import date
        p = None
        if d.get("start") and d.get("end"):
            try:
                p = ReportPeriod(date.fromisoformat(d["start"]), date.fromisoformat(d["end"]))
            except ValueError:
                p = None
        return ExtractedPeriod(status=ExtractionStatus(d["status"]), period=p,
                               source_label=d.get("source_label"), note_ar=d.get("note_ar"),
                               page=d.get("page"))

    return ExtractionResult(
        format_id=payload["format_id"],
        format_verified=bool(payload["format_verified"]),
        glucose_unit=GlucoseUnit(payload["glucose_unit"]),
        report_period=period(payload.get("report_period")),
        metrics_period=period(payload.get("metrics_period")),
        fields=fields,
        checks=[ConsistencyCheck(c["id"], c["passed"], c["message_ar"],
                                 {MetricKey(k) for k in c.get("involved", [])})
                for c in payload.get("checks", [])],
        warnings_ar=list(payload.get("warnings_ar") or []),
        sensor_label=payload.get("sensor_label") or "",
        limited_data_notice=bool(payload.get("limited_data_notice")),
        device_label=payload.get("device_label"),
        report_days_label=payload.get("report_days_label"),
        ai_used=bool(payload.get("ai_used")),
        page_count=int(payload.get("page_count") or 0),
    )


# ---------------------------------------------------------------- upload


@router.post("", status_code=202)
async def upload_report(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    processor: ReportProcessor = Depends(get_processor),
) -> dict:
    settings = session.settings
    # Bound memory use even when the client omits Content-Length.
    data = await file.read(settings.max_upload_bytes + 1)
    await file.close()

    if len(data) > settings.max_upload_bytes:
        raise payload_too_large(
            f"حجم الملف {format_file_size(len(data))} وهو أكبر من الحد المسموح "
            f"({format_file_size(settings.max_upload_bytes)})."
        )

    validation = validate_pdf_bytes(file.filename or "", data, settings.max_upload_bytes)
    if not validation.is_valid:
        if validation.error is PdfValidationError.TOO_LARGE:
            raise payload_too_large(validation.message_ar)
        raise unprocessable(validation.error.value, validation.message_ar)

    record = ReportRecord(
        id=new_id(), user_id=session.user_id, status=ReportStatus.PROCESSING,
        created_at=now_utc(), file_name=file.filename or "report.pdf",
        file_size_bytes=len(data), file_sha256=sha256_of(data),
        provenance="synthetic" if session.is_demo else "real",
    )
    session.repo.create_report(record)
    if not session.is_demo and settings.store_report_files:
        try:
            record.storage_path = session.repo.store_report_file(record, data, settings.supabase_reports_bucket)
            session.repo.save_report(record)
        except Exception:
            record.status = ReportStatus.FAILED
            record.error_ar = "تعذّر حفظ الملف في التخزين الخاص. تحقق من إعداد الحاوية ثم أعد المحاولة."
            session.repo.save_report(record)
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail={"code": "storage_unavailable", "message_ar": record.error_ar}) from None

    repo = session.repo
    target_profile = session.target_profile

    def run() -> None:
        try:
            processor.process(repo, record, data, target_profile)
        except Exception:  # pragma: no cover - last-resort guard
            log.exception("report processing crashed for report %s", record.id)
            record.status = ReportStatus.FAILED
            record.error_ar = "حدث خطأ غير متوقع أثناء معالجة التقرير. حاول الرفع مرة أخرى."
            repo.save_report(record)

    background.add_task(run)
    return {
        "report": record.summary_json(),
        "message_ar": "تم استلام الملف وبدأت المعالجة. سنخبرك فور جاهزية التقرير.",
    }


# ----------------------------------------------------------------- reads


@router.get("")
def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    rows, total = session.repo.list_reports(session.user_id, limit=limit, offset=offset)
    return {
        "items": [r.summary_json() for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/{report_id}")
def get_report(report_id: str, session: Session = Depends(get_session)) -> dict:
    rec = session.repo.get_report(session.user_id, report_id)
    if rec is None:
        raise not_found("لم نعثر على هذا التقرير ضمن تقاريرك.")
    return rec.detail_json()


@router.get("/{report_id}/status")
def report_status(report_id: str, session: Session = Depends(get_session)) -> dict:
    rec = session.repo.get_report(session.user_id, report_id)
    if rec is None:
        raise not_found("لم نعثر على هذا التقرير ضمن تقاريرك.")
    return {
        "id": rec.id, "status": rec.status,
        "status_label_ar": ReportStatus.LABELS_AR.get(rec.status, rec.status),
        "error_ar": rec.error_ar,
        "ready": rec.status in (ReportStatus.READY, ReportStatus.NEEDS_REVIEW),
        "failed": rec.status == ReportStatus.FAILED,
    }


@router.get("/{report_id}/file")
def private_report_file(report_id: str, session: Session = Depends(get_session)) -> dict:
    rec = session.repo.get_report(session.user_id, report_id)
    if rec is None or not rec.storage_path or session.is_demo:
        raise not_found("لا توجد نسخة محفوظة لهذا الملف.")
    return {"url": session.repo.signed_report_url(rec.storage_path, session.settings.supabase_reports_bucket),
            "expires_in_seconds": 300}


@router.get("/{report_id}/metrics")
def report_metrics(report_id: str, session: Session = Depends(get_session)) -> dict:
    rec = session.repo.get_report(session.user_id, report_id)
    if rec is None:
        raise not_found("لم نعثر على هذا التقرير ضمن تقاريرك.")
    return {
        "report_id": rec.id,
        "glucose_unit": rec.glucose_unit,
        "metrics": rec.verified_metrics,
        "extraction": rec.extraction,
        "data_quality": rec.data_quality,
    }


@router.get("/{report_id}/summary")
def report_summary(report_id: str, session: Session = Depends(get_session)) -> dict:
    rec = session.repo.get_report(session.user_id, report_id)
    if rec is None:
        raise not_found("لم نعثر على هذا التقرير ضمن تقاريرك.")
    return {
        "report_id": rec.id,
        "analysis": rec.analysis,
        "ai_summary": rec.ai_summary,
        "warnings_ar": rec.warnings_ar,
        "data_quality": rec.data_quality,
    }


# ----------------------------------------------------------- corrections


@router.patch("/{report_id}/fields")
def update_fields(
    report_id: str,
    body: FieldUpdateBatch,
    session: Session = Depends(get_session),
    processor: ReportProcessor = Depends(get_processor),
) -> dict:
    rec = session.repo.get_report(session.user_id, report_id)
    if rec is None:
        raise not_found("لم نعثر على هذا التقرير ضمن تقاريرك.")
    if not rec.extraction:
        raise bad_request("not_processed", "لم تنتهِ معالجة هذا التقرير بعد.")

    result = _rebuild_extraction(rec.extraction)
    fields = dict(result.fields)

    for upd in body.updates:
        key = MetricKey(upd.metric_key) if upd.metric_key in {k.value for k in MetricKey} else None
        if key is None or key not in fields:
            raise bad_request("unknown_metric", f"مؤشر غير معروف: {upd.metric_key}")
        f = fields[key]
        if upd.mark_unavailable is not None:
            f = f.copy_with(marked_unavailable=upd.mark_unavailable,
                            confirmed=False if upd.mark_unavailable else f.confirmed)
        if upd.corrected_value is not None:
            f = f.copy_with(corrected_value=float(upd.corrected_value), marked_unavailable=False)
        if upd.confirmed is not None:
            f = f.copy_with(confirmed=bool(upd.confirmed))
        fields[key] = f

    result = result.copy_with(fields=fields)

    if body.confirm_all_eligible:
        from ..services.report_service import auto_confirm
        from ..domain.report_parser import apply_consistency_checks
        result = auto_confirm(apply_consistency_checks(result))

    rec = processor.reanalyse(session.repo, rec, result, session.target_profile)
    return rec.detail_json()
