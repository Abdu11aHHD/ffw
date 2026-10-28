"""Report processing pipeline.

upload -> structural validation -> PyMuPDF text -> deterministic parser
      -> [optional Gemini cross-check] -> consistency checks
      -> auto-confirm only fields that passed every deterministic check
      -> verified metrics (+ derived) -> data quality -> rule evaluation
      -> Arabic summary (Gemini, guarded, with deterministic fallback)

Nothing is reported as complete before this pipeline has actually finished.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime

from ..config import Settings
from ..db.models import ReportRecord, ReportStatus
from ..db.repository import Repository, now_utc
from ..domain.extraction import ExtractionResult
from ..domain.report_parser import apply_consistency_checks
from ..domain.metrics import (
    CgmReport,
    DataProvenance,
    DataQuality,
    MetricKey,
    MetricValue,
    ReportPeriod,
    ReportSourceType,
    TargetProfile,
    ValueOrigin,
    VerificationStatus,
)
from ..domain.report_parser import ReportTextParser
from ..domain.rules import RuleEngine
from ..domain.summary_checks import quality_from_summary, with_derived_metrics
from ..domain.units import GlucoseUnit, ar_period
from ..domain.visit_prep import SUMMARY_METRIC_ORDER
from . import notifications as notify
from .gemini import ExplanationContext, GeminiService, GroundedValue
from .pdf_extract import PdfExtractionError, extract_page_texts
from .analysis import analysis_service

log = logging.getLogger("sukkar.reports")


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def auto_confirm(result: ExtractionResult) -> ExtractionResult:
    """Confirm only the fields that passed every deterministic check and were
    not contradicted by the AI. Everything else stays `needs_review` so the
    patient decides."""
    fields = {
        k: (f.copy_with(confirmed=True) if f.eligible_for_bulk_confirm else f)
        for k, f in result.fields.items()
    }
    return result.copy_with(fields=fields)


def verified_metrics_from(result: ExtractionResult) -> dict[MetricKey, MetricValue]:
    metrics: dict[MetricKey, MetricValue] = {}
    for key, f in result.fields.items():
        value = f.effective_value
        if value is None:
            metrics[key] = MetricValue(
                key=key, value=None, unit=f.unit,
                origin=ValueOrigin.EXTRACTED_FROM_REPORT,
                status=VerificationStatus.UNAVAILABLE,
                source_label=f.source_label, source_page=f.source_page,
            )
            continue
        origin = ValueOrigin.USER_CORRECTED if f.is_corrected else ValueOrigin.EXTRACTED_FROM_REPORT
        metrics[key] = MetricValue(
            key=key, value=value, unit=f.unit, origin=origin,
            status=(VerificationStatus.VERIFIED if f.confirmed else VerificationStatus.NEEDS_REVIEW),
            source_label=f.source_label, source_page=f.source_page,
            original_extracted_value=f.extracted_value if f.is_corrected else None,
        )
    return with_derived_metrics(metrics)


def _period_from_json(d: dict | None) -> ReportPeriod | None:
    if not d or not d.get("start") or not d.get("end"):
        return None
    try:
        return ReportPeriod(date.fromisoformat(d["start"]), date.fromisoformat(d["end"]))
    except ValueError:
        return None


def cgm_report_from_record(rec: ReportRecord) -> CgmReport:
    """Rebuild the domain object used by the rule engine and visit preparation."""
    metrics: dict[MetricKey, MetricValue] = {}
    for m in rec.verified_metrics:
        key = MetricKey(m["key"])
        metrics[key] = MetricValue(
            key=key, value=m.get("value"), unit=m.get("unit") or "%",
            origin=ValueOrigin(m.get("origin") or "extracted_from_report"),
            status=VerificationStatus(m.get("status") or "unavailable"),
            source_label=m.get("source_label"), source_page=m.get("source_page"),
            original_extracted_value=m.get("original_extracted_value"),
            note=m.get("note"),
        )
    q = rec.data_quality or {}
    quality = DataQuality(
        days_of_data=q.get("days_of_data"), coverage_percent=q.get("coverage_percent"),
        coverage_source=q.get("coverage_source") or "", sufficient=bool(q.get("sufficient")),
        reasons_ar=list(q.get("reasons_ar") or []),
    )
    return CgmReport(
        id=rec.id, user_id=rec.user_id,
        provenance=DataProvenance(rec.provenance),
        source_type=ReportSourceType.PDF_UPLOAD,
        glucose_unit=GlucoseUnit(rec.glucose_unit),
        metrics=metrics, quality=quality, created_at=rec.created_at,
        report_period=_period_from_json(rec.report_period),
        metrics_period=_period_from_json(rec.metrics_period),
        format_id=rec.format_id, device_label=rec.device_label,
        warnings_ar=list(rec.warnings_ar),
    )


class ReportProcessor:
    def __init__(self, settings: Settings, gemini: GeminiService | None = None,
                 parser: ReportTextParser | None = None,
                 rule_engine: RuleEngine | None = None) -> None:
        self.settings = settings
        self.gemini = gemini or analysis_service(settings)
        self.parser = parser or ReportTextParser()
        self.rule_engine = rule_engine or RuleEngine()

    # -------------------------------------------------------------- run

    def process(self, repo: Repository, rec: ReportRecord, data: bytes,
                target_profile: TargetProfile, allow_ai: bool = True,
                now: datetime | None = None) -> ReportRecord:
        now = now or now_utc()
        try:
            pdf = extract_page_texts(data)
        except PdfExtractionError as exc:
            rec.status = ReportStatus.FAILED
            rec.error_ar = exc.message_ar
            repo.save_report(rec)
            notify.report_failed(repo, rec.user_id, rec.id, exc.message_ar)
            return rec

        result = self.parser.parse(pdf.page_texts)
        if result.is_empty:
            rec.status = ReportStatus.FAILED
            rec.page_count = pdf.page_count
            rec.error_ar = (
                "لم نتعرف على أي مؤشر سكر في هذا الملف. تأكد أنه تقرير حساس أو مضخة "
                "يحتوي صفحة ملخص المؤشرات، وليس وصفة أو تقريرًا مخبريًا."
            )
            repo.save_report(rec)
            notify.report_failed(repo, rec.user_id, rec.id, rec.error_ar)
            return rec

        if allow_ai and self.gemini.configured:
            try:
                result = self.gemini.cross_check_extraction(result, data)
            except Exception as exc:  # never let the optional step fail a report
                log.info("AI cross-check skipped: %s", type(exc).__name__)

        result = auto_confirm(apply_consistency_checks(result))
        rec = self._store_analysis(repo, rec, result, pdf.page_count, target_profile, now)
        notify.report_ready(repo, rec.user_id, rec.id, (rec.analysis or {}).get("outcome_title_ar"))
        return rec

    # ---------------------------------------------- re-run after an edit

    def reanalyse(self, repo: Repository, rec: ReportRecord,
                  result: ExtractionResult, target_profile: TargetProfile,
                  now: datetime | None = None) -> ReportRecord:
        now = now or now_utc()
        return self._store_analysis(repo, rec, apply_consistency_checks(result),
                                    rec.page_count, target_profile, now)

    # ------------------------------------------------------------ store

    def _store_analysis(self, repo: Repository, rec: ReportRecord, result: ExtractionResult,
                        page_count: int, target_profile: TargetProfile,
                        now: datetime) -> ReportRecord:
        metrics = verified_metrics_from(result)
        metrics_period = _period_from_json(result.metrics_period.to_json())
        sensor = metrics.get(MetricKey.SENSOR_ACTIVE)
        quality = quality_from_summary(
            metrics_period=metrics_period,
            printed_sensor_percent=(sensor.value if (sensor and sensor.is_verified) else None),
            sensor_label=result.sensor_label,
            limited_data_notice=result.limited_data_notice,
        )

        rec.page_count = page_count
        rec.format_id = result.format_id
        rec.format_verified = result.format_verified
        rec.device_label = result.device_label
        rec.glucose_unit = result.glucose_unit.value
        rec.report_period = result.report_period.to_json()
        rec.metrics_period = result.metrics_period.to_json()
        rec.warnings_ar = list(result.warnings_ar)
        rec.extraction = result.to_json()
        rec.verified_metrics = [m.to_json() for m in metrics.values()]
        rec.data_quality = quality.to_json()
        rec.error_ar = None
        final_status = ReportStatus.NEEDS_REVIEW if result.has_pending else ReportStatus.READY

        domain_report = cgm_report_from_record(rec)
        evaluation = self.rule_engine.evaluate(domain_report, profile=target_profile, now=now)
        rec.analysis = evaluation.to_json()

        period = domain_report.effective_period
        ctx = ExplanationContext(
            values=[
                GroundedValue(k.label_ar, metrics[k].value, metrics[k].unit)
                for k in SUMMARY_METRIC_ORDER
                if k in metrics and metrics[k].is_verified and metrics[k].value is not None
            ],
            period_label=ar_period(period.start, period.end) if period else None,
            period_days=period.days if period else None,
            missing_ar=list(quality.reasons_ar),
            outcome=evaluation.outcome,
            reference_findings=[{"title_ar": r["rule_title_ar"], "evidence": r["evidence"],
                                 "source_ref": r["source_ref"]}
                                for r in rec.analysis.get("results", []) if r["status"] == "triggered"],
        )
        rec.ai_summary = self.gemini.explain(ctx).to_json()
        rec.status = final_status
        repo.save_report(rec)
        return rec
