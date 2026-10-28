/** طلبات المتابعة: list, create and detail. */

import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Badge, Button, Card, EmptyState, ErrorState, ListSkeleton, Notice, SectionHeader, Toast,
  type Tone,
} from '../components/ui';
import { Icon } from '../components/Icons';
import { ApiError, api } from '../lib/api';
import { arDate, arDateTime } from '../lib/format';
import { useApi } from '../lib/useApi';
import type { FollowUpStatus } from '../lib/types';
import { SukkarHeader, SukkarScreen } from './SukkarChrome';

const STATUS_TONE: Record<FollowUpStatus, Tone> = {
  draft: 'neutral',
  awaiting_review: 'info',
  under_review: 'info',
  more_info_requested: 'warn',
  reviewed: 'ok',
  closed: 'neutral',
};

export function SukkarFollowupList() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi(() => api.followups());

  return (
    <SukkarScreen header={<SukkarHeader title="طلبات المتابعة" subtitle="حالة كل طلب وقراره" />}>
      {loading && <ListSkeleton rows={2} />}
      {error && <ErrorState message={error.messageAr} onRetry={reload} />}

      {data && data.items.length === 0 && (
        <EmptyState
          icon="stethoscope"
          title="لا توجد طلبات متابعة"
          body="بعد مراجعة تقريرك يمكنك طلب مراجعة من مختص تجريبي داخل النموذج الأولي."
          action={<Button onClick={() => navigate('/my-profile/diabetes-journey/reports')}>افتح تقاريري</Button>}
        />
      )}

      {data && data.items.length > 0 && (
        <div className="sp-enter space-y-3">
          {data.items.map((f) => (
            <Card
              key={f.id}
              className="sp-pressable cursor-pointer p-4"
              onClick={() => navigate(`/my-profile/diabetes-journey/followups/${f.id}`)}
            >
              <div className="flex items-start gap-3">
                <span className="grid place-items-center size-10 shrink-0 rounded-xl
                  bg-primary-soft text-primary">
                  <Icon name="stethoscope" size={19} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="sp-ltr text-[13.5px] font-bold text-ink">{f.pseudo_ref}</p>
                  <p className="mt-0.5 line-clamp-2 text-[12.5px] text-ink-2">{f.reason_ar}</p>
                  <p className="mt-0.5 text-[11.5px] text-ink-3">{arDate(f.created_at)}</p>
                </div>
                <Badge tone={STATUS_TONE[f.status]}>{f.status_label_ar}</Badge>
              </div>
            </Card>
          ))}
        </div>
      )}

      <div className="mt-6">
        <Notice tone="warn" title="مراجعة تجريبية">
          طلبات المراجعة هنا لا تصل إلى طبيب حقيقي، ولا تصلح للحالات العاجلة. إذا كان لديك
          قلق عاجل تواصل فورًا مع مقدم الرعاية أو خدمات الطوارئ.
        </Notice>
      </div>
    </SukkarScreen>
  );
}

export function SukkarFollowupNew() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const reportId = params.get('report');
  const [reason, setReason] = useState('');
  const [includeMetrics, setIncludeMetrics] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ text: string; tone: 'ok' | 'danger' } | null>(null);

  const prep = useApi(() => api.visitPrep(reportId ?? undefined), [reportId]);

  async function submit() {
    setBusy(true);
    try {
      const created = await api.createFollowup({
        report_id: reportId, reason_ar: reason.trim(), include_metrics: includeMetrics,
      });
      navigate(`/my-profile/diabetes-journey/followups/${created.id}`, { replace: true });
    } catch (err) {
      setToast({
        text: err instanceof ApiError ? err.messageAr : 'تعذّر إنشاء الطلب.',
        tone: 'danger',
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <SukkarScreen header={<SukkarHeader title="طلب مراجعة" subtitle="راجع ما ستشاركه قبل الإرسال" />}>
      <div className="sp-enter space-y-5">
        <Notice tone="warn" title="مراجعة تجريبية داخل النموذج الأولي">
          لا يصل هذا الطلب إلى طبيب حقيقي ولا يُحجز به موعد حقيقي. إذا كان لديك قلق عاجل على
          صحتك تواصل فورًا مع مقدم الرعاية أو خدمات الطوارئ (997 / 911).
        </Notice>

        <Card className="p-4">
          <label htmlFor="reason" className="mb-2 block text-[13.5px] font-semibold text-ink">
            لماذا ترغب في المراجعة؟
          </label>
          <textarea
            id="reason"
            rows={4}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={1000}
            placeholder="اكتب سببًا موجزًا يساعد المراجع على فهم طلبك."
            className="w-full resize-none rounded-xl border border-line bg-surface-2 px-3 py-2.5
              text-[13.5px] leading-relaxed text-ink placeholder:text-ink-3"
          />
          <p className="sp-ltr mt-1 text-left text-[11.5px] text-ink-3">{reason.length}/1000</p>
        </Card>

        <Card className="p-4">
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={includeMetrics}
              onChange={(e) => setIncludeMetrics(e.target.checked)}
              className="mt-1 size-4 accent-[color:var(--sp-primary)]"
            />
            <span className="min-w-0 flex-1">
              <span className="block text-[13.5px] font-medium text-ink">
                مشاركة المؤشرات الموثّقة مع المراجع
              </span>
              <span className="mt-0.5 block text-[12px] text-ink-2">
                لا يرى المراجع اسمك ولا ملفك كاملًا، بل اللقطة التي تؤكدها هنا فقط.
              </span>
            </span>
          </label>
        </Card>

        {includeMetrics && (
          <section>
            <SectionHeader title="ما سيراه المراجع" />
            {prep.loading && <ListSkeleton rows={1} />}
            {prep.data && (
              <Card className="divide-y divide-line/70 overflow-hidden">
                <div className="px-4 py-3 text-[12.5px] text-ink-3">
                  الفترة: {prep.data.period_ar ?? 'غير محددة'}
                </div>
                {prep.data.metrics.filter((m) => m.value_ar !== 'غير متاح').map((m) => (
                  <div key={m.label_ar} className="flex items-baseline justify-between gap-3 px-4 py-2.5">
                    <span className="text-[13px] text-ink-2">{m.label_ar}</span>
                    <span className="sp-ltr text-[13px] font-semibold text-ink">{m.value_ar}</span>
                  </div>
                ))}
              </Card>
            )}
          </section>
        )}

        <Button full icon="stethoscope" loading={busy} disabled={!reason.trim()}
          onClick={() => void submit()}>
          إرسال الطلب
        </Button>
      </div>

      {toast && <Toast message={toast.text} tone={toast.tone} onDismiss={() => setToast(null)} />}
    </SukkarScreen>
  );
}

export function SukkarFollowupDetail() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi(() => api.followup(id), [id]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ text: string; tone: 'ok' | 'danger' } | null>(null);

  async function act(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    try {
      await fn();
      setToast({ text: done, tone: 'ok' });
      reload();
    } catch (err) {
      setToast({ text: err instanceof ApiError ? err.messageAr : 'تعذّر تنفيذ العملية.', tone: 'danger' });
    } finally {
      setBusy(false);
    }
  }

  return (
    <SukkarScreen header={<SukkarHeader title="طلب المتابعة" subtitle={data?.pseudo_ref} />}>
      {loading && <ListSkeleton rows={3} />}
      {error && <ErrorState message={error.messageAr} onRetry={reload} />}

      {data && (
        <div className="sp-enter space-y-5">
          <Card className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="sp-ltr text-[14px] font-bold text-ink">{data.pseudo_ref}</p>
                <p className="mt-0.5 text-[12px] text-ink-3">{arDateTime(data.created_at)}</p>
              </div>
              <Badge tone={STATUS_TONE[data.status]}>{data.status_label_ar}</Badge>
            </div>
            <p className="mt-3 border-t border-line/70 pt-3 text-[13px] leading-relaxed text-ink-2">
              {data.reason_ar}
            </p>
          </Card>

          {data.patient_message_ar && (
            <Notice tone={data.decision === 'review_required' ? 'warn' : 'info'}
              title={data.decision_label_ar ?? 'قرار المراجع'}>
              {data.patient_message_ar}
            </Notice>
          )}

          {data.appointment && (
            <Card className="sp-pressable cursor-pointer p-4"
              onClick={() => navigate(`/appointments/${data.appointment!.id}`)}>
              <div className="flex items-center gap-3">
                <span className="grid place-items-center size-10 shrink-0 rounded-xl
                  bg-mint-soft text-mint">
                  <Icon name="calendar" size={19} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-semibold text-ink">موعدك التجريبي جاهز</p>
                  <p className="text-[12.5px] text-ink-2">{arDateTime(data.appointment.scheduled_at)}</p>
                </div>
              </div>
              <p className="mt-3 border-t border-line/70 pt-2.5 text-[11.5px] text-ink-3">
                {data.appointment.simulated_label_ar}
              </p>
            </Card>
          )}

          {data.notes.length > 0 && (
            <section>
              <SectionHeader title="ملاحظات المراجع" />
              <Card className="divide-y divide-line/70 overflow-hidden">
                {data.notes.map((n) => (
                  <div key={n.at} className="px-4 py-3">
                    <p className="text-[13px] leading-relaxed text-ink-2">{n.text_ar}</p>
                    <p className="mt-1 text-[11.5px] text-ink-3">{n.author_label} — {arDate(n.at)}</p>
                  </div>
                ))}
              </Card>
            </section>
          )}

          <section>
            <SectionHeader title="اللقطة المشاركة" />
            <Card className="divide-y divide-line/70 overflow-hidden">
              <div className="px-4 py-3 text-[12.5px] text-ink-3">
                الفترة: {data.shared_snapshot.period}
              </div>
              {Object.entries(data.shared_snapshot.items).map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-3 px-4 py-2.5">
                  <span className="text-[13px] text-ink-2">{k}</span>
                  <span className="sp-ltr text-[13px] font-semibold text-ink">{v}</span>
                </div>
              ))}
              {data.shared_snapshot.quality_notes.map((q) => (
                <p key={q} className="px-4 py-2 text-[11.5px] text-ink-3">{q}</p>
              ))}
            </Card>
          </section>

          <section>
            <SectionHeader title="سجل الحالة" />
            <Card className="divide-y divide-line/70 overflow-hidden">
              {data.history.map((h, i) => (
                <div key={`${h.at}-${i}`} className="px-4 py-2.5">
                  <p className="text-[13px] text-ink">
                    {h.from_label_ar ? `${h.from_label_ar} ← ${h.to_label_ar}` : h.to_label_ar}
                  </p>
                  <p className="text-[11.5px] text-ink-3">
                    {arDateTime(h.at)}{h.note_ar ? ` — ${h.note_ar}` : ''}
                  </p>
                </div>
              ))}
            </Card>
          </section>

          <div className="space-y-3">
            {(data.status === 'draft' || data.status === 'awaiting_review') && (
              <Button full variant="danger" loading={busy}
                onClick={() => void act(() => api.withdrawFollowup(id), 'تم سحب الطلب.')}>
                سحب الطلب
              </Button>
            )}
            {data.status === 'reviewed' && (
              <Button full variant="secondary" loading={busy}
                onClick={() => void act(() => api.closeFollowup(id), 'تم إغلاق الطلب.')}>
                إغلاق الطلب
              </Button>
            )}
            {data.report_id && (
              <Button full variant="ghost" onClick={() => navigate(`/my-profile/diabetes-journey/reports/${data.report_id}`)}>
                عرض التقرير المرتبط
              </Button>
            )}
          </div>
        </div>
      )}

      {toast && <Toast message={toast.text} tone={toast.tone} onDismiss={() => setToast(null)} />}
    </SukkarScreen>
  );
}
