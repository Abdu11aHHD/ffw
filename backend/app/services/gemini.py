"""Gemini integration through the official Python SDK (google-genai).

Gemini is used for two bounded jobs:
  1. cross-checking the printed CGM summary fields the deterministic parser
     already read (never as the sole source of a number), and
  2. writing a short Arabic summary of values the backend has already verified.

Structured output is required and validated with Pydantic. Every generated
sentence passes a safety and grounding guard before it reaches the patient.
If the key is missing, the call times out, or validation fails, the service
falls back to deterministic Python output and says so.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..config import Settings
from ..domain.extraction import (
    ExtractedField,
    ExtractionMethod,
    ExtractionResult,
    ExtractionStatus,
    FieldValidation,
    is_plausible,
)
from ..domain.report_parser import apply_consistency_checks
from ..domain.metrics import MetricKey
from ..domain.rules import ReviewOutcome
from ..domain.units import GlucoseUnit, format_number, round_to, parse_glucose_unit

log = logging.getLogger("sukkar.gemini")

EXTRACTION_INSTRUCTION = """You read printed continuous glucose monitoring (CGM) summary reports.
Return ONLY values that are printed in the document. Never calculate, estimate or infer a value.
If a value is not printed, return null for it. Do not return names, dates of birth, serial numbers,
insulin, bolus, carbohydrate or pump-setting values.
Range bands: time_very_low (<54 mg/dL), time_low (54-69), time_in_range (70-180), time_high (181-250),
time_very_high (>250), time_below_range_total (<70), time_above_range_total (>180).
sensor_active is the printed percentage of time the CGM was active/connected.
Percent values use unit "%"; mean_glucose and sd use the report's glucose unit."""

EXPLANATION_INSTRUCTION = """أنت مساعد تعليمي في نموذج أولي اسمه "سكر بلس". اكتب شرحًا عربيًا موجزًا وهادئًا
يعتمد فقط على القيم الموثّقة المرسلة في السياق. لا تضف أي رقم غير موجود في السياق. لا تقدم تشخيصًا،
ولا توصيات علاجية، ولا أي حديث عن الجرعات أو الأدوية، ولا تصف أي قيمة بأنها خطيرة أو غير طبيعية.
إذا كانت قيمة ناقصة فاذكر أنها غير متاحة. اختم بأن الفريق الصحي هو المرجع. لا تتجاوز 120 كلمة."""


# ------------------------------------------------------------ structured IO


class AiField(BaseModel):
    key: str
    value: float | None = None
    unit: str = ""
    page: int | None = None
    label: str | None = None

    @field_validator("key")
    @classmethod
    def known_key(cls, v: str) -> str:
        if v not in {k.value for k in MetricKey}:
            raise ValueError(f"unknown metric key: {v}")
        return v


class AiExtraction(BaseModel):
    glucose_unit: str
    fields: list[AiField] = Field(default_factory=list)

    @field_validator("glucose_unit")
    @classmethod
    def known_unit(cls, v: str) -> str:
        if parse_glucose_unit(v) is None:
            raise ValueError("unknown glucose unit")
        return v


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "glucose_unit": {"type": "string", "enum": ["mg/dL", "mmol/L"]},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": [k.value for k in MetricKey]},
                    "value": {"type": "number", "nullable": True},
                    "unit": {"type": "string"},
                    "page": {"type": "integer", "nullable": True},
                    "label": {"type": "string", "nullable": True},
                },
                "required": ["key", "value", "unit"],
            },
        },
    },
    "required": ["glucose_unit", "fields"],
}


class ExplanationSource(str, Enum):
    AI = "ai"
    LOCAL_TEMPLATE = "local_template"

    @property
    def label_ar(self) -> str:
        return ("تحليل مولّد بالذكاء الاصطناعي — اجتاز فحوص الاستناد إلى الأرقام" if self is ExplanationSource.AI
                else "نص من قالب محلي (دون ذكاء اصطناعي)")


@dataclass(frozen=True)
class Explanation:
    text: str
    source: ExplanationSource
    fallback_reason_ar: str | None = None
    provider: str | None = None
    model: str | None = None
    observations_ar: list[str] = field(default_factory=list)
    questions_ar: list[str] = field(default_factory=list)
    limitations_ar: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "text": self.text,
            "source": self.source.value,
            "source_label_ar": self.source.label_ar,
            "fallback_reason_ar": self.fallback_reason_ar,
            "provider": self.provider, "model": self.model,
            "observations_ar": self.observations_ar,
            "questions_ar": self.questions_ar,
            "limitations_ar": self.limitations_ar,
        }


@dataclass(frozen=True)
class GroundedValue:
    label_ar: str
    value: float
    unit: str

    @property
    def formatted(self) -> str:
        return f"{format_number(self.value)}{'%' if self.unit == '%' else ' ' + self.unit}"

    def to_json(self) -> dict:
        return {"label": self.label_ar, "value": round_to(self.value, 1), "unit": self.unit}


@dataclass
class ExplanationContext:
    values: list[GroundedValue]
    period_label: str | None = None
    period_days: int | None = None
    missing_ar: list[str] = None  # type: ignore[assignment]
    outcome: ReviewOutcome | None = None
    reference_findings: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.missing_ar is None:
            self.missing_ar = []

    def allowed_numbers(self) -> set[float]:
        """Numbers the generated text may contain: grounded values (rounded to
        0, 1 and 2 decimals), general reference target numbers, period length
        and small counting numbers."""
        out: set[float] = set()
        for v in self.values:
            out.update({v.value, round_to(v.value, 0), round_to(v.value, 1), round_to(v.value, 2)})
        if self.period_days is not None:
            out.add(float(self.period_days))
        out.update({14, 70, 180, 54, 250, 4, 1, 25, 5, 36, 2})
        return out

    def to_json(self) -> dict:
        return {
            "period": self.period_label,
            "period_days": self.period_days,
            "verified_values": [v.to_json() for v in self.values],
            "missing": list(self.missing_ar),
            "outcome": self.outcome.value if self.outcome else None,
            "reference_findings": self.reference_findings,
        }


# --------------------------------------------------------------- guardrail


_BANNED = [
    re.compile("جرع"), re.compile("وحد(ة|ات) (من )?(ال)?[إا]نسولين"), re.compile("زد (من )?"),
    re.compile("ارفع جرعة"), re.compile("قلل"), re.compile("قلّل"), re.compile("أوقف"),
    re.compile("توقف عن"), re.compile("غيّ?ر (ال)?دواء"), re.compile("عدّ?ل (ال)?علاج"),
    re.compile(r"\bdos(e|es|ing|age)\b", re.IGNORECASE),
    re.compile(r"units? of insulin", re.IGNORECASE),
    re.compile(r"\b(increase|decrease|reduce|adjust) your\b", re.IGNORECASE),
    re.compile(r"\bstop taking\b", re.IGNORECASE),
    re.compile("تشخيص"), re.compile("مصاب ب"), re.compile("لديك مرض"), re.compile("خطير"),
    re.compile("غير طبيعي"), re.compile("حالة طارئة"),
    re.compile("diagnos", re.IGNORECASE), re.compile(r"\bdangerous\b", re.IGNORECASE),
    re.compile(r"\babnormal\b", re.IGNORECASE),
]

_ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"
_PERSIAN = "۰۱۲۳۴۵۶۷۸۹"


def normalize_digits(s: str) -> str:
    out = []
    for ch in s:
        i = _ARABIC_INDIC.find(ch)
        j = _PERSIAN.find(ch)
        if i >= 0:
            out.append(str(i))
        elif j >= 0:
            out.append(str(j))
        elif ch == "٫":
            out.append(".")
        else:
            out.append(ch)
    return "".join(out)


def validate_ai_text(text: str, allowed: set[float], max_length: int = 1500) -> list[str]:
    """Returns a list of reasons the text must be rejected (empty = accepted)."""
    reasons: list[str] = []
    t = (text or "").strip()
    if not t:
        reasons.append("النص فارغ.")
    if len(t) > max_length:
        reasons.append("النص أطول من المسموح.")
    for pattern in _BANNED:
        if pattern.search(t):
            reasons.append(f"يحتوي النص على صياغة غير مسموحة ({pattern.pattern}).")
    for m in re.finditer(r"\d+(?:\.\d+)?", normalize_digits(t)):
        n = float(m.group(0))
        if not any(abs(a - n) <= 0.051 for a in allowed):
            reasons.append(f"رقم غير مستند إلى البيانات الموثّقة: {m.group(0)}")
    return reasons


def local_template_explanation(ctx: ExplanationContext) -> str:
    """Deterministic Arabic explanation; used when AI is unavailable or rejected."""
    parts: list[str] = []
    head = "هذا ملخص تقرير الحساس" + (f" للفترة {ctx.period_label}" if ctx.period_label else "")
    head += f" ({ctx.period_days} يومًا)." if ctx.period_days is not None else "."
    parts.append(head)
    if not ctx.values:
        parts.append("لا توجد قيم موثّقة لعرضها بعد.")
    else:
        parts.append("القيم الموثّقة:")
        parts.extend(f"• {v.label_ar}: {v.formatted}" for v in ctx.values)
    if ctx.outcome is not None:
        parts.append("")
        parts.append(f"نتيجة القواعد المُعدّة: {ctx.outcome.title_ar}. {ctx.outcome.explanation_ar}")
    if ctx.missing_ar:
        parts.append("")
        parts.append("ملاحظات حول البيانات:")
        parts.extend(f"• {m}" for m in ctx.missing_ar)
    parts.append("هذا شرح تعليمي ولا يغني عن استشارة فريقك الصحي.")
    return "\n".join(parts).strip()


# ----------------------------------------------------------------- client


class GeminiService:
    def __init__(self, settings: Settings, client=None) -> None:
        self.settings = settings
        self._client = client
        self._tried_import = client is not None

    @property
    def configured(self) -> bool:
        return self.settings.gemini_configured

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.configured:
            return None
        if self._tried_import:
            return None
        self._tried_import = True
        try:
            from google import genai  # type: ignore
            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        except Exception as exc:  # pragma: no cover - import/credential issues
            log.warning("Gemini SDK unavailable: %s", type(exc).__name__)
            self._client = None
        return self._client

    # -- 1. extraction cross-check -------------------------------------

    def cross_check_extraction(self, result: ExtractionResult, pdf_bytes: bytes) -> ExtractionResult:
        """Ask Gemini for the same printed fields and reconcile field by field.

        Gemini never introduces a number into a verified metric on its own:
        agreement keeps a field eligible for bulk confirmation, disagreement or
        an AI-only value forces individual confirmation by the patient.
        """
        client = self._get_client()
        if client is None:
            return result
        try:
            from google.genai import types  # type: ignore
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=[
                    # Never transmit the original PDF, names, device identifiers,
                    # filenames or arbitrary source snippets to the AI provider.
                    json.dumps({"glucose_unit": result.glucose_unit.value, "fields": [
                        {"key": k.value, "value": f.extracted_value, "unit": f.unit}
                        for k, f in result.fields.items() if f.extracted_value is not None
                    ]}, ensure_ascii=False),
                    "Map these locally extracted CGM metrics to the required JSON schema. Do not add missing values.",
                ],
                config=types.GenerateContentConfig(
                    system_instruction=EXTRACTION_INSTRUCTION,
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=EXTRACTION_SCHEMA,
                    http_options=types.HttpOptions(timeout=int(self.settings.gemini_timeout_seconds * 1000)),
                ),
            )
            payload = _parse_json_text(getattr(response, "text", None))
            if payload is None:
                return result
            parsed = AiExtraction.model_validate(payload)
        except ValidationError as exc:
            log.info("Gemini extraction rejected by schema validation: %s", exc.error_count())
            return result
        except Exception as exc:  # timeout, transport, quota
            log.info("Gemini extraction unavailable: %s", type(exc).__name__)
            return result

        return reconcile_with_ai(result, parsed)

    # -- 2. Arabic summary ---------------------------------------------

    def explain(self, ctx: ExplanationContext) -> Explanation:
        client = self._get_client()
        if client is None:
            reason = ("لم يُضبط مفتاح خدمة الذكاء الاصطناعي على الخادم."
                      if not self.configured else "تعذّر الوصول إلى خدمة الذكاء الاصطناعي.")
            return Explanation(local_template_explanation(ctx), ExplanationSource.LOCAL_TEMPLATE, reason)
        try:
            from google.genai import types  # type: ignore
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=f"السياق (JSON):\n{json.dumps(ctx.to_json(), ensure_ascii=False)}",
                config=types.GenerateContentConfig(
                    system_instruction=EXPLANATION_INSTRUCTION,
                    temperature=0.2,
                    max_output_tokens=600,
                    http_options=types.HttpOptions(timeout=int(self.settings.gemini_timeout_seconds * 1000)),
                ),
            )
            text = (getattr(response, "text", None) or "").strip()
        except Exception as exc:
            log.info("Gemini explanation unavailable: %s", type(exc).__name__)
            return Explanation(local_template_explanation(ctx), ExplanationSource.LOCAL_TEMPLATE,
                               "تعذّر الوصول إلى خدمة الذكاء الاصطناعي.")

        reasons = validate_ai_text(text, ctx.allowed_numbers())
        if reasons:
            log.info("Gemini explanation rejected by the safety guard (%d reasons)", len(reasons))
            return Explanation(
                local_template_explanation(ctx), ExplanationSource.LOCAL_TEMPLATE,
                "رُفض نص الذكاء الاصطناعي لعدم اجتيازه فحوص السلامة والاستناد إلى البيانات.",
            )
        return Explanation(text, ExplanationSource.AI)


def _parse_json_text(text: str | None):
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


AGREEMENT_TOLERANCE = {"%": 0.11, "mg/dL": 1.01, "mmol/L": 0.06}


def reconcile_with_ai(result: ExtractionResult, ai: AiExtraction) -> ExtractionResult:
    """Field-by-field reconciliation. Deterministic values always win as the
    stored number; the AI only changes how much confirmation a field needs."""
    unit = parse_glucose_unit(ai.glucose_unit) or result.glucose_unit
    by_key: dict[MetricKey, AiField] = {}
    for f in ai.fields:
        key = MetricKey(f.key)
        if f.value is None:
            continue
        if not is_plausible(key, float(f.value), unit):
            continue
        if key in by_key:        # duplicate keys are discarded entirely
            by_key.pop(key, None)
            continue
        by_key[key] = f

    fields: dict[MetricKey, ExtractedField] = {}
    for key, local in result.fields.items():
        ai_field = by_key.get(key)
        if ai_field is None:
            fields[key] = local
            continue
        ai_value = float(ai_field.value)
        if local.extracted_value is None:
            # AI-only value: recorded, but it must be confirmed individually
            # and it is never auto-verified.
            fields[key] = local.copy_with(
                ai_value=ai_value,
                method=ExtractionMethod.AI,
                extraction_status=ExtractionStatus.AMBIGUOUS,
                validation=FieldValidation.NOT_CROSS_CHECKED,
                messages_ar=[*local.messages_ar,
                             "قيمة اقترحها الذكاء الاصطناعي ولم يعثر عليها المحلل النصي — تحتاج تأكيدك."],
            )
            continue
        tol = AGREEMENT_TOLERANCE.get(local.unit, 0.11)
        agree = abs(local.extracted_value - ai_value) <= tol
        fields[key] = local.copy_with(
            ai_value=ai_value,
            method=ExtractionMethod.LOCAL_AND_AI_AGREE if agree else ExtractionMethod.LOCAL_AND_AI_DISAGREE,
            messages_ar=([*local.messages_ar] if agree else
                         [*local.messages_ar,
                          f"اختلفت قراءة الذكاء الاصطناعي ({format_number(ai_value)}) "
                          f"عن القراءة النصية ({format_number(local.extracted_value)})؛ تحقق من التقرير."]),
            confirmed=False if not agree else local.confirmed,
        )

    return apply_consistency_checks(result.copy_with(fields=fields, ai_used=True))
