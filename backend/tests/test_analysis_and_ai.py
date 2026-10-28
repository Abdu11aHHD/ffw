"""Rule engine, appointment preparation, Gemini guards and fallbacks."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.domain.metrics import (
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
from app.domain.rules import ReviewOutcome, RuleEngine, RuleStatus
from app.domain.units import GlucoseUnit
from app.services.gemini import (
    AiExtraction,
    ExplanationContext,
    GeminiService,
    GroundedValue,
    reconcile_with_ai,
    validate_ai_text,
)

NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)


def _metric(key, value, unit="%", status=VerificationStatus.VERIFIED):
    return MetricValue(key=key, value=value, unit=unit,
                       origin=ValueOrigin.EXTRACTED_FROM_REPORT, status=status)


def _report(metrics, days=28, coverage=90.0):
    period = ReportPeriod(date(2026, 9, 1), date(2026, 9, 1 + days - 1))
    return CgmReport(
        id="r1", user_id="u1", provenance=DataProvenance.SYNTHETIC,
        source_type=ReportSourceType.PDF_UPLOAD, glucose_unit=GlucoseUnit.MGDL,
        metrics=metrics,
        quality=DataQuality(days_of_data=days, coverage_percent=coverage,
                            coverage_source="test", sufficient=days >= 14 and coverage >= 70,
                            reasons_ar=[] if (days >= 14 and coverage >= 70) else ["بيانات قليلة"]),
        created_at=NOW, report_period=period, metrics_period=period,
        format_id="omnipod_discover_agp_summary_v1",
    )


# ------------------------------------------------------------------ rules


def test_values_inside_the_reference_targets_give_a_routine_summary():
    report = _report({
        MetricKey.TIME_VERY_LOW: _metric(MetricKey.TIME_VERY_LOW, 0.4),
        MetricKey.TIME_BELOW_RANGE_TOTAL: _metric(MetricKey.TIME_BELOW_RANGE_TOTAL, 2.0),
        MetricKey.TIME_VERY_HIGH: _metric(MetricKey.TIME_VERY_HIGH, 3.0),
    })
    ev = RuleEngine().evaluate(report, profile=TargetProfile.GENERAL_ADULT_T1_T2, now=NOW)
    assert ev.outcome is ReviewOutcome.ROUTINE_SUMMARY
    assert ev.triggered == []


def test_exceeding_a_reference_target_suggests_a_review():
    report = _report({
        MetricKey.TIME_VERY_LOW: _metric(MetricKey.TIME_VERY_LOW, 3.2),
        MetricKey.TIME_BELOW_RANGE_TOTAL: _metric(MetricKey.TIME_BELOW_RANGE_TOTAL, 2.0),
        MetricKey.TIME_VERY_HIGH: _metric(MetricKey.TIME_VERY_HIGH, 3.0),
    })
    ev = RuleEngine().evaluate(report, profile=TargetProfile.GENERAL_ADULT_T1_T2, now=NOW)
    assert ev.outcome is ReviewOutcome.REVIEW_SUGGESTED
    assert [r.rule.id for r in ev.triggered] == ["TBR54-TARGET"]
    assert "ليس تشخيصًا" in ev.outcome.explanation_ar


def test_short_period_is_reported_as_incomplete_not_reassuring():
    report = _report({MetricKey.TIME_VERY_LOW: _metric(MetricKey.TIME_VERY_LOW, 0.1)}, days=5)
    ev = RuleEngine().evaluate(report, profile=TargetProfile.GENERAL_ADULT_T1_T2, now=NOW)
    assert ev.outcome is ReviewOutcome.NEED_MORE_DATA


def test_low_coverage_is_reported_as_incomplete():
    report = _report({MetricKey.TIME_VERY_LOW: _metric(MetricKey.TIME_VERY_LOW, 0.1)}, coverage=52.0)
    ev = RuleEngine().evaluate(report, profile=TargetProfile.GENERAL_ADULT_T1_T2, now=NOW)
    assert ev.outcome is ReviewOutcome.NEED_MORE_DATA


def test_unspecified_target_profile_does_not_invent_targets():
    report = _report({MetricKey.TIME_VERY_LOW: _metric(MetricKey.TIME_VERY_LOW, 9.0)})
    ev = RuleEngine().evaluate(report, profile=TargetProfile.UNSPECIFIED, now=NOW)
    assert ev.outcome is ReviewOutcome.NEED_MORE_DATA
    assert all(r.status is not RuleStatus.TRIGGERED for r in ev.results)


def test_unverified_values_are_never_used_by_a_rule():
    report = _report({
        MetricKey.TIME_VERY_LOW: _metric(MetricKey.TIME_VERY_LOW, 9.0,
                                         status=VerificationStatus.NEEDS_REVIEW),
    })
    ev = RuleEngine().evaluate(report, profile=TargetProfile.GENERAL_ADULT_T1_T2, now=NOW)
    assert ev.triggered == []


def test_episode_rule_is_not_applicable_to_a_printed_summary():
    report = _report({MetricKey.TIME_VERY_LOW: _metric(MetricKey.TIME_VERY_LOW, 0.1)})
    ev = RuleEngine().evaluate(report, profile=TargetProfile.GENERAL_ADULT_T1_T2, now=NOW)
    episode = next(r for r in ev.results if r.rule.id == "EPI54-REPEATED")
    assert episode.status is RuleStatus.NOT_APPLICABLE


def test_urgent_concern_never_waits_for_a_reviewer():
    outcome = RuleEngine.urgent_concern_outcome()
    assert outcome is ReviewOutcome.SEEK_MEDICAL_HELP
    assert "997" in outcome.explanation_ar


def test_every_rule_is_labelled_demonstration_only():
    for rule in RuleEngine().rule_set.rules:
        assert rule.approval.value == "demonstration_only"
        assert rule.source_ref


# ------------------------------------------------------- appointment prep


def test_visit_prep_lists_metrics_limits_and_questions(client, patient_headers, report_pdf):
    from .conftest import upload
    upload(client, patient_headers, report_pdf)
    prep = client.get("/api/v1/visit-prep", headers=patient_headers).json()
    assert prep["period_days"] == 14
    assert prep["metrics"]
    assert prep["questions_ar"]
    assert prep["disclaimer_ar"]
    assert "لا يتضمن تشخيصًا" in prep["disclaimer_ar"]
    sourced = [m for m in prep["metrics"] if m["source_ar"]]
    assert sourced, "metrics must carry their printed source"


def test_visit_prep_refuses_to_compare_a_single_report(client, patient_headers, report_pdf):
    from .conftest import upload
    upload(client, patient_headers, report_pdf)
    prep = client.get("/api/v1/visit-prep", headers=patient_headers).json()
    assert prep["comparison"]["comparable"] is False
    assert prep["comparison"]["reason_ar"]


def test_visit_prep_without_any_report_reports_the_gap(client, patient_headers):
    prep = client.get("/api/v1/visit-prep", headers=patient_headers).json()
    assert prep["report_id"] is None
    assert "لا يوجد تقرير حساس موثّق." in prep["missing_ar"]


def test_overlapping_periods_are_not_compared():
    from app.domain.comparison import compare_latest_cgm_periods
    a = _report({MetricKey.TIME_IN_RANGE: _metric(MetricKey.TIME_IN_RANGE, 60.0)})
    b = _report({MetricKey.TIME_IN_RANGE: _metric(MetricKey.TIME_IN_RANGE, 70.0)})
    result = compare_latest_cgm_periods([a, b])
    assert result.comparable is False
    assert "متداخلتان" in result.reason_ar


def test_different_units_are_not_compared():
    from app.domain.comparison import compare_latest_cgm_periods
    a = _report({MetricKey.TIME_IN_RANGE: _metric(MetricKey.TIME_IN_RANGE, 60.0)})
    b = _report({MetricKey.TIME_IN_RANGE: _metric(MetricKey.TIME_IN_RANGE, 70.0)})
    b = CgmReport(**{**b.__dict__, "glucose_unit": GlucoseUnit.MMOLL,
                     "report_period": ReportPeriod(date(2026, 10, 1), date(2026, 10, 28)),
                     "metrics_period": ReportPeriod(date(2026, 10, 1), date(2026, 10, 28))})
    result = compare_latest_cgm_periods([a, b])
    assert result.comparable is False
    assert "وحدتا" in result.reason_ar


# -------------------------------------------------------------- AI guards


def test_ai_text_with_an_ungrounded_number_is_rejected():
    ctx = ExplanationContext(values=[GroundedValue("الوقت ضمن النطاق", 65.5, "%")])
    reasons = validate_ai_text("الوقت ضمن النطاق 65.5% ومتوسط السكر 212 mg/dL.", ctx.allowed_numbers())
    assert any("غير مستند" in r for r in reasons)


def test_ai_text_mentioning_a_dose_is_rejected():
    ctx = ExplanationContext(values=[])
    assert validate_ai_text("ينصح برفع جرعة الإنسولين.", ctx.allowed_numbers())


def test_ai_text_calling_a_value_dangerous_is_rejected():
    ctx = ExplanationContext(values=[])
    assert validate_ai_text("هذا الرقم خطير جدًا.", ctx.allowed_numbers())


def test_grounded_ai_text_is_accepted():
    ctx = ExplanationContext(values=[GroundedValue("الوقت ضمن النطاق", 65.5, "%")], period_days=14)
    assert validate_ai_text("خلال 14 يومًا كان الوقت ضمن النطاق 65.5%.", ctx.allowed_numbers()) == []


def test_arabic_indic_digits_are_normalised_before_checking():
    ctx = ExplanationContext(values=[GroundedValue("الوقت ضمن النطاق", 65.5, "%")])
    assert any("غير مستند" in r for r in validate_ai_text("القيمة ٢١٢.", ctx.allowed_numbers()))


def test_explanation_falls_back_when_gemini_is_not_configured():
    from app.config import Settings
    service = GeminiService(Settings(gemini_api_key=""))
    ctx = ExplanationContext(values=[GroundedValue("الوقت ضمن النطاق", 65.5, "%")])
    out = service.explain(ctx)
    assert out.source.value == "local_template"
    assert "مفتاح" in out.fallback_reason_ar


def test_explanation_falls_back_when_gemini_raises():
    from app.config import Settings

    class Boom:
        class models:
            @staticmethod
            def generate_content(**kwargs):
                raise TimeoutError("gemini timeout")

    service = GeminiService(Settings(gemini_api_key="k"), client=Boom())
    out = service.explain(ExplanationContext(values=[]))
    assert out.source.value == "local_template"
    assert "تعذّر الوصول" in out.fallback_reason_ar


def test_ai_agreement_keeps_a_field_eligible_for_bulk_confirmation(report_text):
    from app.domain.report_parser import ReportTextParser
    result = ReportTextParser().parse([report_text])
    ai = AiExtraction(glucose_unit="mg/dL", fields=[
        {"key": "mean_glucose", "value": 168, "unit": "mg/dL"},
    ])
    merged = reconcile_with_ai(result, ai)
    field = merged.fields[MetricKey.MEAN_GLUCOSE]
    assert field.method.value == "local_and_ai_agree"
    assert field.eligible_for_bulk_confirm is True
    assert field.extracted_value == 168  # the deterministic value is kept


def test_ai_disagreement_forces_individual_confirmation(report_text):
    from app.domain.report_parser import ReportTextParser
    result = ReportTextParser().parse([report_text])
    ai = AiExtraction(glucose_unit="mg/dL", fields=[
        {"key": "mean_glucose", "value": 199, "unit": "mg/dL"},
    ])
    merged = reconcile_with_ai(result, ai)
    field = merged.fields[MetricKey.MEAN_GLUCOSE]
    assert field.method.value == "local_and_ai_disagree"
    assert field.eligible_for_bulk_confirm is False
    assert field.extracted_value == 168
    assert field.ai_value == 199


def test_ai_cannot_introduce_an_implausible_value(report_text):
    from app.domain.report_parser import ReportTextParser
    result = ReportTextParser().parse([report_text])
    ai = AiExtraction(glucose_unit="mg/dL", fields=[
        {"key": "mean_glucose", "value": 9000, "unit": "mg/dL"},
    ])
    merged = reconcile_with_ai(result, ai)
    assert merged.fields[MetricKey.MEAN_GLUCOSE].ai_value is None
    assert merged.fields[MetricKey.MEAN_GLUCOSE].extracted_value == 168


def test_invalid_gemini_payload_is_rejected_by_the_schema():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        AiExtraction.model_validate({"glucose_unit": "bananas", "fields": []})
    with pytest.raises(pydantic.ValidationError):
        AiExtraction.model_validate({"glucose_unit": "mg/dL",
                                     "fields": [{"key": "heart_rate", "value": 70, "unit": "bpm"}]})


def test_extraction_cross_check_is_skipped_when_gemini_fails(report_text):
    from app.config import Settings
    from app.domain.report_parser import ReportTextParser

    class Boom:
        class models:
            @staticmethod
            def generate_content(**kwargs):
                raise RuntimeError("unavailable")

    result = ReportTextParser().parse([report_text])
    service = GeminiService(Settings(gemini_api_key="k"), client=Boom())
    merged = service.cross_check_extraction(result, b"%PDF-")
    assert merged.ai_used is False
    assert merged.fields[MetricKey.MEAN_GLUCOSE].extracted_value == 168
