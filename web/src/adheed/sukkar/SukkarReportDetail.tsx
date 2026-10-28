/** A single report: extracted values with their source, the deterministic
 *  checks, the Arabic summary, the outcome and the follow-up action. */

import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Badge, Button, Card, ErrorState, ListSkeleton, Notice, SectionHeader, Toast, type Tone,
} from '../components/ui';
import { Icon } from '../components/Icons';
import { ApiError, api } from '../lib/api';
import { arDate, arPeriod, formatMetric } from '../lib/format';
import { useApi } from '../lib/useApi';
import type { ExtractedFieldJson, ReportDetail, ReviewOutcome } from '../lib/types';
import { SukkarHeader, SukkarScreen } from './SukkarChrome';

const OUTCOME_TONE: Record<ReviewOutcome, Tone> = {
  routine_summary: 'ok',
  review_suggested: 'warn',
  need_more_data: 'info',
  seek_medical_help: 'danger',
};

const RANGE_KEYS = ['time_very_low', 'time_low', 'time_in_range', 'time_high', 'time_very_high'] as const;
const RANGE_COLORS: Record<string, string> = {
  time_very_low: '#a32e4e',
  time_low: '#e0704e',
  time_in_range: '#1e8fe0',
  time_high: '#b98200',
  time_very_high: '#97470f',
};

function RangeBar({ report }: { report: ReportDetail }) {
  const values = RANGE_KEYS.map((k) => {
    const m = report.verified_metrics.find((v) => v.key === k);
    return { key: k, label: m?.label_ar ?? k, value: m?.status === 'verified' ? m.value : null };
  });
  if (values.some((v) => v.value === null)) return null;
  const total = values.reduce((a, v) => a + (v.value ?? 0), 0) || 100;
  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-pill" role="img"
        aria-label="توزيع الوقت على نطاقات السكر">
        {values.map((v) => (
          <span key={v.key} style={{ width: `${((v.value ?? 0) / total) * 100}%`,
            background: RANGE_COLORS[v.key] }} />
        ))}
      </div>
      <ul className="mt-3 space-y-1.5">
        {values.map((v) => (
          <li key={v.key} className="flex items-center gap-2 text-[12.5px]">
            <span className="size-2.5 shrink-0 rounded-sm" style={{ background: RANGE_COLORS[v.key] }} />
            <span className="flex-1 text-ink-2">{v.label}</span>
            <span className="sp-ltr font-semibold text-ink">{v.value}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function FieldRow({ f, onConfirm, onUnavailable, busy }: {
  f: ExtractedFieldJson;
  onConfirm: (value: number | null) => void;
  onUnavailable: () => void;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(f.effective_value ?? ''));
  const needsAction = f.verification === 'needs_review';

  return (
    <div className="px-4 py-3.5">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[13.5px] font-medium text-ink">{f.label_ar}</p>
          <p className="mt-0.5 text-[12px] text-ink-3">
            {f.source_label ?? 'غير موجود في التقرير'}
            {f.source_page ? ` — صفحة ${f.source_page}` : ''}
          </p>
        </div>
        <div className="text-left">
          <p className="sp-ltr text-[14px] font-bold text-ink">
            {f.effective_value === null ? '—' : formatMetric(f.effective_value, f.unit)}
          </p>
          <p className="text-[11px] text-ink-3">{f.method_label_ar}</p>
        </div>
      </div>

      {f.corrected_value !== null && f.extracted_value !== null && (
        <p className="mt-1.5 text-[11.5px] text-ink-3">
          القيمة الأصلية المستخرجة: <span className="sp-ltr">{f.extracted_value}</span>
        </p>
      )}
      {f.ai_value !== null && (
        <p className="mt-1 text-[11.5px] text-ink-3">
          قراءة الذكاء الاصطناعي: <span className="sp-ltr">{f.ai_value}</span>
        </p>
      )}
      {f.messages_ar.map((m) => (
        <p key={m} className="mt-1.5 text-[12px] text-warn">{m}</p>
      ))}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Badge tone={f.verification === 'verified' ? 'ok' : f.verification === 'unavailable' ? 'neutral' : 'warn'}>
          {f.verification === 'verified' ? 'موثّق'
            : f.verification === 'unavailable' ? 'غير متاح' : 'يحتاج تحقق'}
        </Badge>
        <Badge tone={f.validation === 'valid' ? 'ok' : f.validation === 'inconsistent' ? 'danger' : 'neutral'}>
          {f.validation_label_ar}
        </Badge>
      </div>

      {needsAction && (
        <div className="mt-3">
          {editing ? (
            <div className="flex gap-2">
              <input
                type="number"
                step="0.1"
                dir="ltr"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                aria-label={`تصحيح ${f.label_ar}`}
                className="sp-ltr w-28 rounded-lg border border-line bg-surface-2 px-2.5 py-2
                  text-[13px] text-ink"
              />
              <Button className="!min-h-[38px] !px-3 !text-[13px]" loading={busy}
                onClick={() => { onConfirm(draft === '' ? null : Number(draft)); setEditing(false); }}>
                حفظ وتأكيد
              </Button>
              <Button variant="ghost" className="!min-h-[38px] !px-3 !text-[13px]"
                onClick={() => setEditing(false)}>إلغاء</Button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {f.effective_value !== null && (
                <Button variant="secondary" className="!min-h-[38px] !px-3 !text-[13px]" loading={busy}
                  onClick={() => onConfirm(null)}>تأكيد القيمة</Button>
              )}
              <Button variant="ghost" className="!min-h-[38px] !px-3 !text-[13px]"
                onClick={() => { setDraft(String(f.effective_value ?? '')); setEditing(true); }}>
                تصحيح
              </Button>
              <Button variant="ghost" className="!min-h-[38px] !px-3 !text-[13px]" loading={busy}
                onClick={onUnavailable}>غير متاح</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SukkarReportDetail() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, reload, setData } = useApi(() => api.report(id), [id]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ text: string; tone: 'ok' | 'danger' } | null>(null);
  const [showAllFields, setShowAllFields] = useState(false);

  const fields = useMemo(() => {
    const all = data?.extraction?.fields ?? [];
    const found = all.filter((f) => f.extraction_status !== 'not_found');
    return showAllFields ? all : found;
  }, [data, showAllFields]);

  const pending = (data?.extraction?.fields ?? []).filter((f) => f.verification === 'needs_review');

  async function patch(updates: Parameters<typeof api.updateFields>[1], confirmAll = false) {
    setBusy(true);
    try {
      const next = await api.updateFields(id, updates, confirmAll);
      setData(next);
      setToast({ text: 'تم تحديث التقرير وإعادة الفحوص.', tone: 'ok' });
    } catch (err) {
      setToast({ text: err instanceof ApiError ? err.messageAr : 'تعذّر الحفظ.', tone: 'danger' });
    } finally {
      setBusy(false);
    }
  }

  return (
    <SukkarScreen header={<SukkarHeader title="تفاصيل التقرير" subtitle="كل قيمة ومصدرها" />}>
      {loading && <ListSkeleton rows={3} />}
      {error && <ErrorState message={error.messageAr} onRetry={reload} />}

      {data && data.status === 'processing' && (
        <Notice tone="info" icon="clock" title="جارٍ تجهيز تقريرك">
          لم تنتهِ المعالجة بعد. حدّث الصفحة بعد لحظات.
        </Notice>
      )}

      {data && data.status === 'failed' && (
        <div className="space-y-4">
          <Notice tone="danger" title="تعذّرت معالجة هذا الملف">{data.error_ar}</Notice>
          <Button full icon="upload" onClick={() => navigate('/my-profile/diabetes-journey/upload')}>رفع ملف آخر</Button>
        </div>
      )}

      {data && (data.status === 'ready' || data.status === 'needs_review') && (
        <div className="sp-enter space-y-6">
          {/* ------------------------------------------------ outcome */}
          {data.analysis && (
            <Card className="p-4">
              <div className="flex items-start gap-3">
                <span className="grid place-items-center size-10 shrink-0 rounded-xl
                  bg-primary-soft text-primary">
                  <Icon name="spark" size={20} />
                </span>
                <div className="min-w-0 flex-1">
                  <Badge tone={OUTCOME_TONE[data.analysis.outcome]}>
                    {data.analysis.outcome_title_ar}
                  </Badge>
                  <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
                    {data.analysis.outcome_explanation_ar}
                  </p>
                </div>
              </div>
              {data.analysis.reasons_ar.length > 0 && (
                <ul className="mt-3 space-y-1.5 border-t border-line/70 pt-3">
                  {data.analysis.reasons_ar.map((r) => (
                    <li key={r} className="flex gap-2 text-[12.5px] text-ink-2">
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-warn" />
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {/* ------------------------------------------------ period */}
          <Card className="p-4">
            <div className="grid grid-cols-2 gap-3 text-[12.5px]">
              <div>
                <p className="text-ink-3">فترة المؤشرات</p>
                <p className="mt-0.5 font-semibold text-ink">
                  {data.metrics_period?.start
                    ? arPeriod(data.metrics_period.start, data.metrics_period.end)
                    : 'غير محددة'}
                </p>
              </div>
              <div>
                <p className="text-ink-3">عدد الأيام</p>
                <p className="sp-ltr mt-0.5 font-semibold text-ink">
                  {data.data_quality?.days_of_data ?? '—'}
                </p>
              </div>
              <div>
                <p className="text-ink-3">تغطية الحساس</p>
                <p className="sp-ltr mt-0.5 font-semibold text-ink">
                  {data.data_quality?.coverage_percent != null
                    ? `${data.data_quality.coverage_percent}%` : '—'}
                </p>
              </div>
              <div>
                <p className="text-ink-3">تنسيق التقرير</p>
                <p className="mt-0.5 font-semibold text-ink">
                  {data.format_verified ? 'مُتحقَّق منه' : 'غير مُتحقَّق منه'}
                </p>
              </div>
            </div>
            {data.device_label && (
              <p className="mt-3 border-t border-line/70 pt-2.5 text-[12px] text-ink-3">
                الجهاز كما طُبع: <span className="sp-ltr">{data.device_label}</span>
              </p>
            )}
          </Card>

          {/* ----------------------------------------------- ranges */}
          <section>
            <SectionHeader title="توزيع نطاقات السكر" />
            <Card className="p-4">
              <RangeBar report={data} />
            </Card>
          </section>

          {/* --------------------------------------------- summary */}
          {data.ai_summary && (
            <section>
              <SectionHeader title="ملخص التقرير" />
              <Card className="p-4" data-testid="ai-analysis">
                <p className="whitespace-pre-line text-[13.5px] leading-relaxed text-ink-2">
                  {data.ai_summary.text}
                </p>
                {[
                  {title:'ماذا يوضح التقرير؟',items:data.ai_summary.observations_ar},
                  {title:'أسئلة مقترحة لموعدك',items:data.ai_summary.questions_ar},
                  {title:'حدود هذا التحليل',items:data.ai_summary.limitations_ar},
                ].filter(section => section.items?.length).map(section => <div key={section.title} className="mt-4 border-t border-line pt-3">
                  <h3 className="text-[14px] font-bold text-ink">{section.title}</h3>
                  <ul className="mt-2 space-y-2 text-[13px] text-ink-2">{section.items?.map(item => <li key={item}>• {item}</li>)}</ul>
                </div>)}
                <p className="mt-3 border-t border-line/70 pt-2.5 text-[11.5px] text-ink-3">
                  {data.ai_summary.source_label_ar}
                  {data.ai_summary.source === 'ai' && data.ai_summary.model ? ` · ${data.ai_summary.provider} · ${data.ai_summary.model}` : ''}
                  {data.ai_summary.fallback_reason_ar ? ` — ${data.ai_summary.fallback_reason_ar}` : ''}
                </p>
                <Button variant="secondary" loading={busy} className="mt-3 !text-[13px]" onClick={() => void patch([])}>
                  إعادة تحليل التقرير
                </Button>
              </Card>
            </section>
          )}

          {/* ----------------------------- pending field confirmations */}
          {pending.length > 0 && (
            <Notice tone="warn" title={`${pending.length} قيمة تحتاج تأكيدك`}>
              <p className="mb-2">
                لم تجتز هذه القيم كل الفحوص الحتمية، لذلك لا تدخل في الملخص قبل أن تؤكدها.
              </p>
              <Button variant="secondary" className="!min-h-[38px] !px-3 !text-[13px]" loading={busy}
                onClick={() => void patch([], true)}>
                تأكيد كل ما اجتاز الفحوص
              </Button>
            </Notice>
          )}

          {/* ------------------------------------------- extracted */}
          <section>
            <SectionHeader
              title="القيم المستخرجة ومصادرها"
              actionLabel={showAllFields ? 'إخفاء غير الموجودة' : 'عرض كل المؤشرات'}
              onAction={() => setShowAllFields((v) => !v)}
            />
            <Card className="divide-y divide-line/70 overflow-hidden">
              {fields.map((f) => (
                <FieldRow
                  key={f.key}
                  f={f}
                  busy={busy}
                  onConfirm={(value) => void patch([{
                    metric_key: f.key,
                    ...(value === null ? {} : { corrected_value: value }),
                    confirmed: true,
                  }])}
                  onUnavailable={() => void patch([{ metric_key: f.key, mark_unavailable: true }])}
                />
              ))}
            </Card>
          </section>

          {/* ------------------------------------------- checks */}
          {data.extraction && data.extraction.checks.length > 0 && (
            <section>
              <SectionHeader title="فحوص الاتساق" />
              <Card className="divide-y divide-line/70 overflow-hidden">
                {data.extraction.checks.map((c) => (
                  <div key={c.id} className="flex items-start gap-2.5 px-4 py-3">
                    <span className={`mt-0.5 shrink-0
                      ${c.passed === true ? 'text-ok' : c.passed === false ? 'text-danger' : 'text-ink-3'}`}>
                      <Icon name={c.passed === true ? 'check' : c.passed === false ? 'alert' : 'info'} size={17} />
                    </span>
                    <p className="text-[12.5px] leading-relaxed text-ink-2">{c.message_ar}</p>
                  </div>
                ))}
              </Card>
            </section>
          )}

          {/* ------------------------------------------- warnings */}
          {data.warnings_ar.length > 0 && (
            <Notice tone="neutral" title="ملاحظات حول التقرير">
              <ul className="list-disc space-y-1 pr-4">
                {data.warnings_ar.map((w) => <li key={w}>{w}</li>)}
              </ul>
            </Notice>
          )}

          {/* ------------------------------------------- actions */}
          <div className="space-y-3">
            <Button full variant="mint" icon="clipboard"
              onClick={() => navigate(`/my-profile/diabetes-journey/visit-prep/${data.id}`)}>
              جهّز أسئلتي للموعد
            </Button>
            <Button full variant="secondary" icon="stethoscope"
              onClick={() => navigate(`/my-profile/diabetes-journey/followups/new?report=${data.id}`)}>
              طلب مراجعة مختص
            </Button>
          </div>

          <p className="px-2 pb-2 text-center text-[11.5px] leading-relaxed text-ink-3">
            رُفع في {arDate(data.created_at)} — {data.file_name}
          </p>
        </div>
      )}

      {toast && <Toast message={toast.text} tone={toast.tone} onDismiss={() => setToast(null)} />}
    </SukkarScreen>
  );
}
