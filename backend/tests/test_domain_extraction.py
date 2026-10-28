"""Deterministic extraction, validation and consistency checks."""

from __future__ import annotations

from app.domain.extraction import PdfValidationError, validate_pdf_bytes
from app.domain.metrics import MetricKey
from app.domain.report_parser import DISCOVER_FORMAT_ID, GENERIC_FORMAT_ID, ReportTextParser
from app.domain.summary_checks import run_summary_checks
from app.domain.units import GlucoseUnit, format_number, round_to, to_mgdl

from .conftest import make_image_only_pdf, make_pdf


def test_parses_the_verified_discover_layout(report_text):
    result = ReportTextParser().parse([report_text])
    assert result.format_id == DISCOVER_FORMAT_ID
    assert result.format_verified is True
    assert result.found_count == 12
    assert result.fields[MetricKey.MEAN_GLUCOSE].extracted_value == 168
    assert result.fields[MetricKey.MEAN_GLUCOSE].unit == "mg/dL"
    assert result.fields[MetricKey.TIME_IN_RANGE].extracted_value == 65.5
    assert result.fields[MetricKey.SENSOR_ACTIVE].extracted_value == 88
    assert result.report_period.period.days == 14


def test_every_value_keeps_its_source(report_text):
    result = ReportTextParser().parse([report_text])
    found = [f for f in result.fields.values() if f.extracted_value is not None]
    assert found
    for f in found:
        assert f.source_label, f"{f.key} lost its printed label"
        assert f.source_page == 1
        assert f.source_text


def test_goal_lines_are_never_read_as_values(report_text):
    """'Goal: <4%' and friends must not become metrics."""
    result = ReportTextParser().parse([report_text])
    assert result.fields[MetricKey.TIME_BELOW_RANGE_TOTAL].extracted_value == 4.5
    assert result.fields[MetricKey.TIME_VERY_LOW].extracted_value == 1.4


def test_all_six_consistency_checks_pass_on_the_fixture(report_text):
    result = ReportTextParser().parse([report_text])
    by_id = {c.id: c for c in result.checks}
    assert set(by_id) == {"band_sum", "tbr_total", "tar_total", "triple_sum", "gmi_mean", "cv_sd_mean"}
    assert all(c.passed is True for c in result.checks)


def test_inconsistent_report_marks_the_involved_fields(report_text):
    broken = report_text.replace("7.3%", "9.9%")  # GMI no longer matches the mean
    result = ReportTextParser().parse([broken])
    gmi_check = next(c for c in result.checks if c.id == "gmi_mean")
    assert gmi_check.passed is False
    assert result.fields[MetricKey.GMI].validation.value == "inconsistent"
    assert result.fields[MetricKey.GMI].eligible_for_bulk_confirm is False


def test_missing_values_are_none_never_zero():
    checks = run_summary_checks({MetricKey.TIME_IN_RANGE: 70.0})
    band_sum = next(c for c in checks if c.id == "band_sum")
    assert band_sum.passed is None  # not evaluable, never "passed"


def test_unverified_generic_layout_requires_individual_confirmation():
    pdf_lines = [
        "Glucose Report 2026-01-01 - 2026-01-28",
        "Average Glucose 150 mg/dL",
        "Time in Range 62 %",
        "Very Low 1 %",
    ]
    result = ReportTextParser().parse(["\n".join(pdf_lines)])
    assert result.format_id == GENERIC_FORMAT_ID
    assert result.format_verified is False
    for f in result.fields.values():
        assert f.eligible_for_bulk_confirm is False


def test_rejects_non_pdf_extension():
    r = validate_pdf_bytes("report.docx", b"%PDF-1.7 ... %%EOF")
    assert r.error is PdfValidationError.UNSUPPORTED_TYPE
    assert "PDF" in r.message_ar


def test_rejects_empty_and_truncated_files():
    assert validate_pdf_bytes("a.pdf", b"").error is PdfValidationError.EMPTY
    assert validate_pdf_bytes("a.pdf", b"%PDF-1.7 no end here").error is PdfValidationError.TRUNCATED


def test_rejects_oversized_file():
    big = b"%PDF-1.7" + b"0" * 200 + b"%%EOF"
    r = validate_pdf_bytes("a.pdf", big, max_bytes=50)
    assert r.error is PdfValidationError.TOO_LARGE


def test_rejects_file_that_is_not_a_pdf_despite_the_extension():
    r = validate_pdf_bytes("a.pdf", b"hello world" * 10 + b"%%EOF")
    assert r.error is PdfValidationError.NOT_PDF


def test_scanned_pdf_explains_that_ocr_is_required():
    from app.services.pdf_extract import PdfExtractionError, extract_page_texts
    import pytest
    with pytest.raises(PdfExtractionError) as exc:
        extract_page_texts(make_image_only_pdf())
    assert "OCR" in exc.value.message_ar


def test_pymupdf_reads_the_real_fixture_pdf(report_pdf):
    from app.services.pdf_extract import extract_page_texts
    text = extract_page_texts(report_pdf)
    assert text.page_count >= 1
    result = ReportTextParser().parse(text.page_texts)
    assert result.format_id == DISCOVER_FORMAT_ID
    assert result.fields[MetricKey.MEAN_GLUCOSE].extracted_value == 168


def test_unit_conversion_and_formatting():
    assert round(to_mgdl(5.5, GlucoseUnit.MMOLL), 2) == 99.1
    assert to_mgdl(100, GlucoseUnit.MGDL) == 100
    assert format_number(7.30) == "7.3"
    assert format_number(30.0) == "30"
    assert round_to(2.345, 2) == 2.35
