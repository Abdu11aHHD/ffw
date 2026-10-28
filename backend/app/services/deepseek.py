"""Grounded Arabic interpretation using DeepSeek's official chat API.

Only locally verified, structured metrics leave the backend. The PDF, source
snippets, names, file names, patient IDs and reasoning output are never sent,
stored or logged. Model output cannot change extracted values or workflow rules.
"""
import json
import logging
import re
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import Settings
from ..domain.extraction import ExtractionResult
from .gemini import (Explanation, ExplanationContext, ExplanationSource,
                     local_template_explanation, validate_ai_text)

log = logging.getLogger("adheed.deepseek")
ENDPOINT = "https://api.deepseek.com/chat/completions"


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text_ar: str = Field(min_length=1, max_length=300)
    metric_labels: list[str] = Field(min_length=1, max_length=6)


class ReportInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary_ar: str = Field(min_length=1, max_length=1200)
    observations: list[Observation] = Field(max_length=4)
    questions_ar: list[str] = Field(min_length=1, max_length=4)
    limitations_ar: list[str] = Field(min_length=1, max_length=4)


INSTRUCTIONS = """You explain a CGM summary report in friendly, clear Arabic for appointment preparation.
Return only a JSON object following the supplied schema. All strings must be Arabic.
Use Arabic prose; English is allowed only for standard metric acronyms and units (GMI, CV, SD, mg/dL, mmol/L).
Explain useful supported patterns in the VERIFIED metrics, not merely a list of numbers.
The deterministic outcome is authoritative. Never contradict or downgrade it.
Missing data must be acknowledged; never infer a missing metric or the time of an episode
from aggregate percentages. A CGM summary cannot tell you what happened overnight or after a meal.
Do not invent causes, diagnoses, history, dates, medications or recommendations to change treatment.
Do not prescribe, adjust insulin, give doses, or provide emergency triage.
Do not assert that a patient is healthy or safe. Summarize limitations and practical questions
to discuss with the clinician. Every observation must cite one or more exact metric_labels
from verified_values; reference only numbers actually present in those values or period_days.
You may explain only reference thresholds supplied in reference_findings.evidence; these are
general reference goals selected by Python, never the patient's individually prescribed goals.
Do not introduce other targets, new computed numbers, or new percentages.
Avoid the words تشخيص, جرعة, جرعات, خطير even in a negated disclaimer. For limitations say
"الملخص إجمالي ولا يحدد توقيت التغيرات أو أسبابها، وتُناقش التفاصيل مع الفريق الصحي."
No numbered lists. No markdown. Do not add any keys outside this JSON schema:
STRICT LENGTH LIMITS: summary_ar at most 1000 characters; observations at most 4;
questions_ar between 1 and 4; limitations_ar between 1 and 4; each list text at most
250 characters. Choose the most useful few items. Do not exceed these counts.
{\"summary_ar\":\"short grounded explanation\",\"observations\":[{\"text_ar\":\"supported pattern\",\"metric_labels\":[\"exact label\"]}],
\"questions_ar\":[\"question for the appointment\"],\"limitations_ar\":[\"what the available data cannot establish\"]}
"""


class DeepSeekService:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    @property
    def configured(self) -> bool:
        return self.settings.deepseek_configured

    def cross_check_extraction(self, result: ExtractionResult, pdf_bytes: bytes) -> ExtractionResult:
        # Numerical extraction is entirely deterministic; never send the PDF.
        return result

    def fallback(self, ctx: ExplanationContext, reason: str) -> Explanation:
        return Explanation(local_template_explanation(ctx), ExplanationSource.LOCAL_TEMPLATE,
                           reason, provider="deepseek", model=self.settings.deepseek_model)

    def explain(self, ctx: ExplanationContext) -> Explanation:
        if not self.configured:
            return self.fallback(ctx, "لم يُضبط مفتاح DeepSeek؛ هذا ملخص محلي من Python.")
        if not ctx.values:
            return self.fallback(ctx, "لا توجد مؤشرات موثّقة كافية لإرسالها إلى DeepSeek.")
        # No period dates are necessary to explain an aggregate report. Retain only its duration.
        context = {"verified_values": [v.to_json() for v in ctx.values],
                   "period_days": ctx.period_days,
                   "outcome": ctx.outcome.value if ctx.outcome else None,
                   "missing": list(ctx.missing_ar), "reference_findings": ctx.reference_findings}
        body = {"model": self.settings.deepseek_model, "stream": False,
                "thinking": {"type": "enabled"}, "reasoning_effort": "high",
                "response_format": {"type": "json_object"}, "max_tokens": 8192,
                "messages": [{"role": "system", "content": INSTRUCTIONS + "\nJSON Schema:\n" + json.dumps(ReportInterpretation.model_json_schema(), ensure_ascii=False)},
                             {"role": "user", "content": json.dumps(context, ensure_ascii=False)}]}
        try:
            # Never follow redirects with credentials, and never log response bodies.
            with httpx.Client(timeout=self.settings.deepseek_timeout_seconds,
                              transport=self.transport, follow_redirects=False) as client:
                response = client.post(ENDPOINT,
                    headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}",
                             "Content-Type": "application/json"}, json=body)
                response.raise_for_status()
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") != "stop":
                return self.fallback(ctx, "لم يكتمل رد DeepSeek؛ عُرض الملخص المحلي.")
            parsed = ReportInterpretation.model_validate_json(choice["message"]["content"])
            labels = {v.label_ar for v in ctx.values}
            if any(set(o.metric_labels) - labels for o in parsed.observations):
                return self.fallback(ctx, "تضمن رد DeepSeek مصدرًا غير موجود ضمن المؤشرات الموثّقة.")
            texts = [parsed.summary_ar, *[o.text_ar for o in parsed.observations],
                     *parsed.questions_ar, *parsed.limitations_ar]
            allowed = {n for v in ctx.values for n in (v.value, round(v.value, 1), round(v.value, 2))}
            for label in labels:
                allowed.update(float(n) for n in re.findall(r"\d+(?:\.\d+)?", label))
            for finding in ctx.reference_findings:
                allowed.update(float(n) for n in re.findall(r"\d+(?:\.\d+)?", json.dumps(finding.get("evidence", {}), ensure_ascii=False)))
            if ctx.period_days is not None: allowed.add(float(ctx.period_days))
            if any(len(t) > 1200 for t in texts) or validate_ai_text("\n".join(texts), allowed, max_length=4500):
                return self.fallback(ctx, "لم يجتز رد DeepSeek فحوص الاستناد إلى البيانات؛ عُرض الملخص المحلي.")
            return Explanation(parsed.summary_ar, ExplanationSource.AI,
                provider="deepseek", model=self.settings.deepseek_model,
                observations_ar=[o.text_ar for o in parsed.observations],
                questions_ar=parsed.questions_ar, limitations_ar=parsed.limitations_ar)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            log.info("DeepSeek unavailable (HTTP %d)", status)
            reason = {401:"مفتاح DeepSeek غير صالح أو غير مخوّل.",
                      402:"رصيد DeepSeek غير كافٍ.",429:"خدمة DeepSeek مشغولة أو بلغت حد الطلبات."}.get(status,"تعذّر الحصول على تحليل DeepSeek.")
            return self.fallback(ctx, reason + " عُرض الملخص المحلي.")
        except httpx.TimeoutException:
            log.info("DeepSeek timed out; using local summary")
            return self.fallback(ctx, "انتهت مهلة انتظار DeepSeek؛ عُرض الملخص المحلي ويمكنك إعادة التحليل.")
        except ValidationError as exc:
            log.info("DeepSeek schema rejected: %s", [(e['loc'], e['type']) for e in exc.errors(include_input=False)])
            return self.fallback(ctx, "رد DeepSeek لم يطابق بنية التحليل المطلوبة؛ عُرض الملخص المحلي.")
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            log.info("DeepSeek response unavailable or invalid (%s)", type(exc).__name__)
            return self.fallback(ctx, "تعذّر اكتمال تحليل DeepSeek أو التحقق من بنيته؛ عُرض الملخص المحلي.")
