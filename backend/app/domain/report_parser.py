"""Deterministic extraction of summary metrics from CGM report PDF text.

Ported from packages/sukkar_core/lib/src/extraction/report_parser.dart.
Text is obtained with PyMuPDF on the server (app/services/pdf_extract.py).

Supported layouts:
  * omnipod_discover_agp_summary_v1 - the "N-Day Summary" page of the Omnipod
    Discover HCP report (Omnipod 5 & Dexcom G7). Verified against the real
    report supplied for this project (layout only; no values from it are
    stored in this repository).
  * generic_agp_unverified - best-effort label search for other AGP-style
    reports. Never verified against a real file; every value must be
    confirmed individually by the user.

Personal data on the report (name, date of birth, serial numbers) is never
read into a field. Insulin, bolus, carbohydrate and pump-setting values are
deliberately ignored: Sukkar Plus does not work with dosing information.
"""

from __future__ import annotations

import re
from datetime import date

from .extraction import (
    NOT_FOUND_PERIOD,
    ExtractedField,
    ExtractedPeriod,
    ExtractionMethod,
    ExtractionResult,
    ExtractionStatus,
    FieldValidation,
    is_plausible,
)
from .metrics import MetricKey, ReportPeriod
from .summary_checks import SummaryTolerances, run_summary_checks
from .units import GlucoseUnit, parse_glucose_unit, to_mgdl

DISCOVER_FORMAT_ID = "omnipod_discover_agp_summary_v1"
GENERIC_FORMAT_ID = "generic_agp_unverified"

_PCT_LINE = re.compile(r"^(\d{1,3}(?:[.,]\d+)?)\s*%$")
_UNIT_LINE = re.compile(r"^(\d{1,3}(?:[.,]\d+)?)\s*(mg/dL|mmol/L)$", re.IGNORECASE)
_BAND = re.compile(r"^(\d{1,3}(?:\.\d+)?)\s*%\s+(Very Low|Low|Very High|High)$", re.IGNORECASE)
_TRIPLE = re.compile(r"^(\d{1,3}(?:\.\d+)?)%\s+(\d{1,3}(?:\.\d+)?)%\s+(\d{1,3}(?:\.\d+)?)%$")
_SLASH_RANGE = re.compile(r"(\d{2}/\d{2}/\d{4})\s*[–—-]\s*(\d{2}/\d{2}/\d{4})")
_DAY_HEADER = re.compile(r"^(\d{1,3})-Day Summary$")
_CONNECTED_SENSOR = re.compile(r"^Connected Sensor Time\s+(\d{1,3}(?:\.\d+)?)\s*%$")

BAND_LABELS = {
    MetricKey.TIME_VERY_LOW: "Very Low (<54 mg/dL)",
    MetricKey.TIME_LOW: "Low (54-69 mg/dL)",
    MetricKey.TIME_HIGH: "High (181-250 mg/dL)",
    MetricKey.TIME_VERY_HIGH: "Very High (>250 mg/dL)",
}

_TRIPLE_LABEL = "Time in Ranges summary row (below / in range / above)"


def _lines(t: str) -> list[str]:
    t = (t.replace(" ", " ").replace("ﬁ", "fi")
          .replace("ﬂ", "fl").replace("−", "-"))
    out = []
    for raw in re.split(r"\r?\n", t):
        line = re.sub(r"\s+", " ", raw).strip()
        if line:
            out.append(line)
    return out


def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", "."))
    except (TypeError, ValueError):
        return None


def _slash_date(s: str, day_first: bool) -> date | None:
    parts = s.split("/")
    if len(parts) != 3:
        return None
    try:
        a, b, y = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    d, m = (a, b) if day_first else (b, a)
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _period(a: str, b: str, day_first: bool) -> ReportPeriod | None:
    s = _slash_date(a, day_first)
    e = _slash_date(b, day_first)
    if s is None or e is None or e < s:
        return None
    return ReportPeriod(s, e)


def _after(lines: list[str], i: int, pattern: re.Pattern, lookahead: int = 2):
    """Value on one of the next `lookahead` lines after a label line."""
    for j in range(i + 1, min(i + lookahead, len(lines) - 1) + 1):
        m = pattern.match(lines[j])
        if m:
            return m, j
    return None


class ReportTextParser:
    def parse(self, page_texts: list[str]) -> ExtractionResult:
        pages = [_lines(t) for t in page_texts]
        all_text = "\n".join(line for p in pages for line in p)
        is_discover = "Glucose Mgmt Indicator" in all_text and "Time in Ranges" in all_text
        result = self._parse_discover(pages) if is_discover else self._parse_generic(pages)
        return result.copy_with(page_count=len(page_texts))

    # ---------------------------------------------- Omnipod Discover (v1)

    def _parse_discover(self, pages: list[list[str]]) -> ExtractionResult:
        summary_idx = next(
            (i for i, p in enumerate(pages) if "Glucose Metrics" in p and "Time in Ranges" in p), -1
        )
        if summary_idx < 0:
            summary_idx = 0
        lines = pages[summary_idx]
        page = summary_idx + 1

        warnings: list[str] = []
        raw: dict[MetricKey, tuple[float, str, str]] = {}  # value, source label, source text
        ambiguous: dict[MetricKey, str] = {}
        unit = GlucoseUnit.MGDL
        report_days: int | None = None
        device: str | None = None
        limited = False
        report_a = report_b = sensor_a = sensor_b = None
        bands: dict[MetricKey, list[float]] = {}
        triples: list[list[float]] = []

        for i, line in enumerate(lines):
            hdr = _DAY_HEADER.match(line)
            if hdr:
                report_days = int(hdr.group(1))

            if report_a is None and "Report Generated" in line:
                m = _SLASH_RANGE.search(line)
                if m:
                    report_a, report_b = m.group(1), m.group(2)

            if line.startswith("Sensor data is only available from"):
                m = _SLASH_RANGE.search(line)
                if m:
                    sensor_a, sensor_b = m.group(1), m.group(2)

            if "limited or no data" in line:
                limited = True

            if line.startswith("Device Use |"):
                device = line[len("Device Use |"):].replace("®", "").strip()

            def take(key: MetricKey, pattern: re.Pattern, label: str, idx: int = i) -> None:
                nonlocal unit
                found = _after(lines, idx, pattern)
                if not found:
                    return
                m, j = found
                v = _num(m.group(1))
                if v is None:
                    return
                if pattern is _UNIT_LINE:
                    u = parse_glucose_unit(m.group(2))
                    if key is MetricKey.MEAN_GLUCOSE and u is not None:
                        unit = u
                raw[key] = (v, label, f"{label} / {lines[j]}")

            if line == "Average Glucose":
                take(MetricKey.MEAN_GLUCOSE, _UNIT_LINE, line)
            elif line == "Glucose Mgmt Indicator (GMI)":
                take(MetricKey.GMI, _PCT_LINE, line)
            elif line == "Glucose Variability (CV*)":
                take(MetricKey.CV, _PCT_LINE, line)
            elif line == "Standard Deviation (SD)":
                take(MetricKey.SD, _UNIT_LINE, line)

            cs = _CONNECTED_SENSOR.match(line)
            if cs:
                raw[MetricKey.SENSOR_ACTIVE] = (_num(cs.group(1)), "Connected Sensor Time", line)

            b = _BAND.match(line)
            if b:
                name = b.group(2).lower()
                key = {
                    "very low": MetricKey.TIME_VERY_LOW,
                    "low": MetricKey.TIME_LOW,
                    "very high": MetricKey.TIME_VERY_HIGH,
                }.get(name, MetricKey.TIME_HIGH)
                bands.setdefault(key, []).append(_num(b.group(1)))

            t = _TRIPLE.match(line)
            if t:
                triples.append([_num(t.group(1)), _num(t.group(2)), _num(t.group(3))])

        for k, vals in bands.items():
            if len(set(vals)) == 1:
                raw[k] = (vals[0], BAND_LABELS[k], f"{vals[0]}% {BAND_LABELS[k]}")
            else:
                ambiguous[k] = "ظهرت للفئة أكثر من قيمة في الصفحة."

        # The "Time in Range" percentage is printed without a label on the same
        # line as the TBR and TAR totals ("5.4% 82.8% 11.8%"). Accept a triple
        # only when it reconciles with the band values.
        vl = raw.get(MetricKey.TIME_VERY_LOW, (None,))[0]
        lo = raw.get(MetricKey.TIME_LOW, (None,))[0]
        hi = raw.get(MetricKey.TIME_HIGH, (None,))[0]
        vh = raw.get(MetricKey.TIME_VERY_HIGH, (None,))[0]

        def reconciles(t: list[float]) -> bool:
            sum_ok = abs((t[0] + t[1] + t[2]) - 100) <= SummaryTolerances.BAND_SUM
            below_ok = vl is None or lo is None or abs(t[0] - (vl + lo)) <= SummaryTolerances.TOTAL_VS_BANDS
            above_ok = hi is None or vh is None or abs(t[2] - (hi + vh)) <= SummaryTolerances.TOTAL_VS_BANDS
            return sum_ok and below_ok and above_ok

        matching = [t for t in triples if reconciles(t)]
        bands_complete = None not in (vl, lo, hi, vh)

        def assign_triple(t: list[float], src: str) -> None:
            raw[MetricKey.TIME_BELOW_RANGE_TOTAL] = (t[0], _TRIPLE_LABEL, src)
            raw[MetricKey.TIME_IN_RANGE] = (t[1], "Time in Range (70-180 mg/dL)", src)
            raw[MetricKey.TIME_ABOVE_RANGE_TOTAL] = (t[2], _TRIPLE_LABEL, src)

        if len(matching) == 1:
            t = matching[0]
            assign_triple(t, f"{t[0]}% {t[1]}% {t[2]}%")
            if not bands_complete:
                ambiguous[MetricKey.TIME_IN_RANGE] = (
                    "قيمة الوقت ضمن النطاق مطبوعة دون عنوان، ولم يمكن مطابقتها مع جميع الفئات."
                )
        elif len(matching) > 1:
            ambiguous[MetricKey.TIME_IN_RANGE] = "وُجد أكثر من صف محتمل لقيمة الوقت ضمن النطاق."
        else:
            sum100 = [t for t in triples if abs((t[0] + t[1] + t[2]) - 100) <= SummaryTolerances.BAND_SUM]
            if len(sum100) == 1:
                t = sum100[0]
                assign_triple(t, f"{t[0]}% {t[1]}% {t[2]}%")
                ambiguous[MetricKey.TIME_IN_RANGE] = (
                    "صف الملخص لا يتطابق مع قيم الفئات المطبوعة؛ قارن القيم بالتقرير."
                )

        # Periods. The supplied report prints DD/MM/YYYY; the orientation is
        # confirmed against the "N-Day Summary" header.
        report_period = NOT_FOUND_PERIOD
        metrics_period = NOT_FOUND_PERIOD
        day_first = True
        if report_a and report_b:
            df = _period(report_a, report_b, True)
            mf = _period(report_a, report_b, False)
            if df is not None and (report_days is None or df.days == report_days):
                report_period = ExtractedPeriod(
                    status=ExtractionStatus.FOUND, period=df,
                    source_label=f"{report_a}–{report_b}", page=page,
                    note_ar=(f"تطابق مع عنوان التقرير ({report_days} يومًا)." if report_days else None),
                )
            elif mf is not None and report_days is not None and mf.days == report_days:
                day_first = False
                report_period = ExtractedPeriod(
                    status=ExtractionStatus.FOUND, period=mf,
                    source_label=f"{report_a}–{report_b}", page=page,
                    note_ar="تنسيق التاريخ شهر/يوم.",
                )
            else:
                report_period = ExtractedPeriod(
                    status=ExtractionStatus.AMBIGUOUS, period=df or mf,
                    source_label=f"{report_a}–{report_b}", page=page,
                    note_ar="تعذّر التأكد من تنسيق تاريخ فترة التقرير.",
                )

        if sensor_a and sensor_b:
            sp = _period(sensor_a, sensor_b, day_first)
            inside = (
                sp is not None and report_period.period is not None
                and sp.start >= report_period.period.start and sp.end <= report_period.period.end
            )
            metrics_period = ExtractedPeriod(
                status=ExtractionStatus.FOUND if (sp is not None and inside) else ExtractionStatus.AMBIGUOUS,
                period=sp, source_label=f"{sensor_a}–{sensor_b}", page=page,
                note_ar="يذكر التقرير أن بيانات الحساس متاحة فقط في هذه الفترة وأن المؤشرات محسوبة عليها.",
            )
            warnings.append(
                f"المؤشرات في هذا التقرير محسوبة على فترة توفر بيانات الحساس ({sensor_a}–{sensor_b}) "
                "وليس على كامل فترة التقرير."
            )
        else:
            metrics_period = report_period

        if limited:
            warnings.append("يذكر التقرير أن بعض الأيام بياناتها محدودة أو غير موجودة.")
        warnings.append(
            "لا يقرأ التطبيق بيانات الإنسولين أو إعدادات المضخة الموجودة في التقرير، "
            "ولا يقدّم أي توصية بشأن الجرعات."
        )
        warnings.append("يحتوي ملف PDF على ملخصات مطبوعة فقط؛ لم يُعِد التطبيق بناء القراءات التفصيلية.")

        return _finish(
            format_id=DISCOVER_FORMAT_ID, format_verified=True, unit=unit, raw=raw,
            ambiguous=ambiguous, page=page, report_period=report_period,
            metrics_period=metrics_period, warnings=warnings,
            sensor_label="نسبة اتصال الحساس (Connected Sensor Time)",
            limited=limited, device=device, report_days=report_days,
        )

    # ------------------------------------------------ generic (unverified)

    def _parse_generic(self, pages: list[list[str]]) -> ExtractionResult:
        raw: dict[MetricKey, tuple[float, str, str]] = {}
        ambiguous: dict[MetricKey, str] = {}
        unit = GlucoseUnit.MGDL
        page: int | None = None

        goal = re.compile(r"goal|target:|greater than|less than|هدف", re.IGNORECASE)
        labels = {
            MetricKey.MEAN_GLUCOSE: re.compile(r"(average|mean) glucose", re.IGNORECASE),
            MetricKey.GMI: re.compile(r"glucose management indicator|\bGMI\b", re.IGNORECASE),
            MetricKey.CV: re.compile(r"coefficient of variation|glucose variability|%\s?CV", re.IGNORECASE),
            MetricKey.SENSOR_ACTIVE: re.compile(
                r"time cgm (is )?active|sensor (usage|wear|active)|connected sensor time", re.IGNORECASE),
        }
        value_with_unit = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*(mg/dL|mmol/L)", re.IGNORECASE)
        value_pct = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")

        for p, lines in enumerate(pages):
            for i, line in enumerate(lines):
                for key, pattern in labels.items():
                    if key in raw:
                        continue
                    lm = pattern.search(line)
                    if not lm:
                        continue
                    wants_unit = key is MetricKey.MEAN_GLUCOSE
                    for j in range(i, min(i + 2, len(lines) - 1) + 1):
                        cand = line[lm.end():] if j == i else lines[j]
                        if goal.search(cand):
                            continue
                        m = (value_with_unit if wants_unit else value_pct).search(cand)
                        if m:
                            v = _num(m.group(1))
                            if v is None:
                                continue
                            if wants_unit:
                                unit = parse_glucose_unit(m.group(2)) or unit
                            raw[key] = (v, line, lines[j])
                            page = page or (p + 1)
                            break

                if goal.search(line):
                    continue

                lower = line.lower()
                band: MetricKey | None = None
                if re.search(r"\bvery low\b", lower):
                    band = MetricKey.TIME_VERY_LOW
                elif re.search(r"\bvery high\b", lower):
                    band = MetricKey.TIME_VERY_HIGH
                elif re.search(r"\b(in range|target range|time in range)\b", lower):
                    band = MetricKey.TIME_IN_RANGE
                elif re.search(r"\blow\b", lower):
                    band = MetricKey.TIME_LOW
                elif re.search(r"\bhigh\b", lower):
                    band = MetricKey.TIME_HIGH

                if band is not None:
                    pcts = [x for x in (_num(m.group(1)) for m in value_pct.finditer(line)) if x is not None]
                    if len(pcts) == 1:
                        if band in raw and raw[band][0] != pcts[0]:
                            ambiguous[band] = "ظهرت للفئة أكثر من قيمة."
                        else:
                            raw[band] = (pcts[0], line, line)
                            page = page or (p + 1)

        period = NOT_FOUND_PERIOD
        all_text = "\n".join(line for p in pages for line in p)
        iso = re.search(r"(\d{4}-\d{2}-\d{2})\s*[–—-]+\s*(\d{4}-\d{2}-\d{2})", all_text)
        if iso:
            try:
                s = date.fromisoformat(iso.group(1))
                e = date.fromisoformat(iso.group(2))
                if e >= s:
                    period = ExtractedPeriod(status=ExtractionStatus.FOUND, period=ReportPeriod(s, e),
                                             source_label=iso.group(0))
            except ValueError:
                pass
        else:
            m = _SLASH_RANGE.search(all_text)
            if m:
                df = _period(m.group(1), m.group(2), True)
                mf = _period(m.group(1), m.group(2), False)
                conflicting = (df is not None and mf is not None and df != mf)
                period = ExtractedPeriod(
                    status=(ExtractionStatus.AMBIGUOUS if (conflicting or (df is None and mf is None))
                            else ExtractionStatus.FOUND),
                    period=df or mf, source_label=m.group(0),
                    note_ar=("تنسيق التاريخ يحتمل يوم/شهر أو شهر/يوم؛ يرجى التحقق." if conflicting else None),
                )

        return _finish(
            format_id=GENERIC_FORMAT_ID, format_verified=False, unit=unit, raw=raw,
            ambiguous=ambiguous, page=page, report_period=period, metrics_period=period,
            warnings=[
                "تنسيق التقرير غير مُتحقَّق منه. القيم استُخرجت بأفضل جهد ويجب تأكيد كل قيمة على حدة.",
                "يحتوي ملف PDF على ملخصات مطبوعة فقط؛ لم يُعِد التطبيق بناء القراءات التفصيلية.",
            ],
            sensor_label="نسبة عمل الحساس", limited=False, device=None, report_days=None,
        )


def _finish(
    *, format_id: str, format_verified: bool, unit: GlucoseUnit,
    raw: dict[MetricKey, tuple[float, str, str]], ambiguous: dict[MetricKey, str],
    page: int | None, report_period: ExtractedPeriod, metrics_period: ExtractedPeriod,
    warnings: list[str], sensor_label: str, limited: bool,
    device: str | None, report_days: int | None,
) -> ExtractionResult:
    fields: dict[MetricKey, ExtractedField] = {}
    for key in MetricKey:
        unit_label = unit.label if key in (MetricKey.MEAN_GLUCOSE, MetricKey.SD) else "%"
        r = raw.get(key)
        if key in ambiguous:
            fields[key] = ExtractedField(
                key=key, extracted_value=(r[0] if r else None), unit=unit_label,
                extraction_status=ExtractionStatus.AMBIGUOUS,
                validation=FieldValidation.NOT_CROSS_CHECKED,
                method=ExtractionMethod.LOCAL_TEXT, source_page=page,
                source_label=(r[1] if r else None), source_text=(r[2] if r else None),
                messages_ar=[ambiguous[key]],
            )
            continue
        if r is None:
            fields[key] = ExtractedField.not_found(key, unit_label)
            continue
        plausible = is_plausible(key, r[0], unit)
        fields[key] = ExtractedField(
            key=key, extracted_value=r[0], unit=unit_label,
            extraction_status=ExtractionStatus.FOUND,
            validation=(FieldValidation.OUT_OF_RANGE if not plausible
                        else (FieldValidation.VALID if format_verified else FieldValidation.NOT_CROSS_CHECKED)),
            method=ExtractionMethod.LOCAL_TEXT, source_page=page,
            source_label=r[1], source_text=r[2],
            messages_ar=[] if plausible else ["القيمة خارج النطاق المعقول لهذا المؤشر."],
        )

    result = ExtractionResult(
        format_id=format_id, format_verified=format_verified, glucose_unit=unit,
        report_period=report_period, metrics_period=metrics_period, fields=fields,
        checks=[], warnings_ar=warnings, sensor_label=sensor_label,
        limited_data_notice=limited, device_label=device, report_days_label=report_days,
    )
    return apply_consistency_checks(result)


def apply_consistency_checks(r: ExtractionResult) -> ExtractionResult:
    """Re-runs deterministic cross-checks on the current effective values and
    marks involved fields inconsistent when a check fails. Used after parsing,
    after AI reconciliation and after every user correction."""
    values: dict[MetricKey, float | None] = {}
    for k, f in r.fields.items():
        v = f.effective_value
        if v is None or f.validation is FieldValidation.OUT_OF_RANGE:
            values[k] = None
        elif k in (MetricKey.MEAN_GLUCOSE, MetricKey.SD) and r.glucose_unit is GlucoseUnit.MMOLL:
            values[k] = to_mgdl(v, GlucoseUnit.MMOLL)
        else:
            values[k] = v

    checks = run_summary_checks(values)
    failing: dict[MetricKey, list[str]] = {}
    for c in checks:
        if c.passed is False:
            for k in c.involved:
                failing.setdefault(k, []).append(c.message_ar)

    fields: dict[MetricKey, ExtractedField] = {}
    for k, f in r.fields.items():
        base = [m for m in f.messages_ar if not m.startswith("تحقق: ")]
        if f.effective_value is None or f.validation is FieldValidation.OUT_OF_RANGE:
            fields[k] = f.copy_with(messages_ar=base)
        elif k in failing:
            fields[k] = f.copy_with(
                validation=FieldValidation.INCONSISTENT, confirmed=False,
                messages_ar=[*base, *(f"تحقق: {m}" for m in failing[k])],
            )
        elif f.validation is FieldValidation.INCONSISTENT:
            # A previous inconsistency was resolved (e.g. by a correction).
            fields[k] = f.copy_with(
                validation=(FieldValidation.VALID if r.format_verified else FieldValidation.NOT_CROSS_CHECKED),
                messages_ar=base,
            )
        else:
            fields[k] = f.copy_with(messages_ar=base)

    return r.copy_with(fields=fields, checks=checks)
