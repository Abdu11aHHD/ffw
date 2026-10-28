/** Reviewer dashboard — a wider desktop layout, outside the phone canvas.
 *  Every call here hits the role-protected /reviewer endpoints; the UI is a
 *  convenience, never the security boundary. */

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Badge, Button, Card, ErrorState, ListSkeleton, Notice, Toast, type Tone } from '../components/ui';
import { ChevronRight, Icon } from '../components/Icons';
import { ApiError, api } from '../lib/api';
import { arDateTime } from '../lib/format';
import { useApi } from '../lib/useApi';
import { useSession } from '../lib/session';
import type { FollowUpStatus } from '../lib/types';

const STATUS_TONE: Record<FollowUpStatus, Tone> = {
  draft: 'neutral', awaiting_review: 'info', under_review: 'info',
  more_info_requested: 'warn', reviewed: 'ok', closed: 'neutral',
};

function ReviewerFrame({ title, back, children }: {
  title: string; back?: boolean; children: React.ReactNode;
}) {
  const navigate = useNavigate();
  const { profile, signOut } = useSession();
  return (
    <div className="min-h-dvh bg-bg">
      <header className="sticky top-0 z-20 border-b border-line bg-bg/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-5 py-4">
          {back && (
            <button type="button" onClick={() => navigate('/reviewer')} aria-label="رجوع"
              className="sp-pressable grid size-9 place-items-center rounded-xl text-ink">
              <ChevronRight size={22} />
            </button>
          )}
          <span className="grid size-9 place-items-center rounded-xl bg-primary-soft text-primary">
            <Icon name="stethoscope" size={19} />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-[18px] font-bold text-ink">{title}</h1>
            <p className="text-[12px] text-ink-3">لوحة المراجع — {profile?.display_name ?? 'مراجع'}</p>
          </div>
          <Button variant="secondary" className="!min-h-[38px] !px-3 !text-[13px]"
            onClick={() => { signOut(); navigate('/reviewer', { replace: true }); }}>
            خروج
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-6">{children}</main>
    </div>
  );
}

export function ReviewerDashboard() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi(() => api.reviewerQueue());

  return (
    <ReviewerFrame title="طلبات المراجعة">
      <Notice tone="warn" title="مراجعة تجريبية">
        هذه لوحة عرض داخل نموذج أولي. القرارات المسجّلة هنا لا تمثّل رأيًا طبيًا، والمواعيد
        التي تُنشأ بعدها مواعيد تجريبية لا تُحجز في أي منشأة صحية.
      </Notice>

      <div className="mt-5">
        {loading && <ListSkeleton rows={3} />}
        {error && <ErrorState message={error.messageAr} onRetry={reload} />}
        {data && data.items.length === 0 && (
          <Card className="p-8 text-center">
            <p className="text-[14px] text-ink-2">لا توجد طلبات في قائمة المراجعة حاليًا.</p>
          </Card>
        )}
        {data && data.items.length > 0 && (
          <div className="overflow-hidden rounded-card border border-line">
            <table className="w-full border-collapse text-right">
              <thead className="bg-surface-2 text-[12.5px] text-ink-3">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">الطلب</th>
                  <th scope="col" className="px-4 py-3 font-medium">السبب</th>
                  <th scope="col" className="px-4 py-3 font-medium">القواعد</th>
                  <th scope="col" className="px-4 py-3 font-medium">آخر تحديث</th>
                  <th scope="col" className="px-4 py-3 font-medium">الحالة</th>
                  <th scope="col" className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-surface text-[13px]">
                {data.items.map((f) => (
                  <tr key={f.id} className="hover:bg-surface-2">
                    <td className="sp-ltr px-4 py-3 font-semibold text-ink">{f.pseudo_ref}</td>
                    <td className="max-w-[280px] truncate px-4 py-3 text-ink-2">{f.reason_ar}</td>
                    <td className="sp-ltr px-4 py-3 text-ink-3">
                      {f.rule_ids.length ? f.rule_ids.join(', ') : '—'}
                    </td>
                    <td className="px-4 py-3 text-ink-3">{arDateTime(f.updated_at)}</td>
                    <td className="px-4 py-3">
                      <Badge tone={STATUS_TONE[f.status]}>{f.status_label_ar}</Badge>
                    </td>
                    <td className="px-4 py-3 text-left">
                      <Button variant="secondary" className="!min-h-[36px] !px-3 !text-[12.5px]"
                        onClick={() => navigate(`/reviewer/requests/${f.id}`)}>
                        فتح
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </ReviewerFrame>
  );
}

export function ReviewerRequest() {
  const { id = '' } = useParams();
  const { data, error, loading, reload } = useApi(() => api.reviewerRequest(id), [id]);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ text: string; tone: 'ok' | 'danger' } | null>(null);

  async function act(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    try {
      await fn();
      setToast({ text: done, tone: 'ok' });
      setNote('');
      reload();
    } catch (err) {
      setToast({ text: err instanceof ApiError ? err.messageAr : 'تعذّر تنفيذ العملية.', tone: 'danger' });
    } finally {
      setBusy(false);
    }
  }

  return (
    <ReviewerFrame title="تفاصيل الطلب" back>
      {loading && <ListSkeleton rows={3} />}
      {error && <ErrorState message={error.messageAr} onRetry={reload} />}

      {data && (
        <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          {/* --------------------------------------------- left column */}
          <div className="space-y-5">
            <Card className="p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="sp-ltr text-[16px] font-bold text-ink">{data.pseudo_ref}</p>
                  <p className="mt-0.5 text-[12.5px] text-ink-3">
                    أُنشئ {arDateTime(data.created_at)} — {data.trigger_label_ar}
                  </p>
                </div>
                <Badge tone={STATUS_TONE[data.status]}>{data.status_label_ar}</Badge>
              </div>
              <p className="mt-4 border-t border-line pt-4 text-[13.5px] leading-relaxed text-ink-2">
                {data.reason_ar}
              </p>
              <p className="mt-3 text-[12px] text-ink-3">
                لا تُعرض هوية المريض للمراجع. المعروض هو اللقطة التي وافق على مشاركتها فقط.
              </p>
            </Card>

            <Card className="overflow-hidden">
              <p className="border-b border-line px-5 py-3 text-[14px] font-bold text-ink">
                اللقطة المشاركة
              </p>
              <div className="px-5 py-3 text-[12.5px] text-ink-3">
                الفترة: {data.shared_snapshot.period}
              </div>
              <div className="divide-y divide-line">
                {Object.entries(data.shared_snapshot.items).map(([k, v]) => (
                  <div key={k} className="flex items-baseline justify-between gap-4 px-5 py-2.5">
                    <span className="text-[13px] text-ink-2">{k}</span>
                    <span className="sp-ltr text-[13px] font-semibold text-ink">{v}</span>
                  </div>
                ))}
              </div>
              {data.shared_snapshot.quality_notes.length > 0 && (
                <ul className="border-t border-line px-5 py-3">
                  {data.shared_snapshot.quality_notes.map((q) => (
                    <li key={q} className="text-[11.5px] text-ink-3">• {q}</li>
                  ))}
                </ul>
              )}
            </Card>

            {data.report?.extraction && (
              <Card className="overflow-hidden">
                <p className="border-b border-line px-5 py-3 text-[14px] font-bold text-ink">
                  القيم المستخرجة ومصادرها
                </p>
                <table className="w-full border-collapse text-right text-[12.5px]">
                  <thead className="bg-surface-2 text-ink-3">
                    <tr>
                      <th scope="col" className="px-5 py-2 font-medium">المؤشر</th>
                      <th scope="col" className="px-5 py-2 font-medium">القيمة</th>
                      <th scope="col" className="px-5 py-2 font-medium">المصدر</th>
                      <th scope="col" className="px-5 py-2 font-medium">التحقق</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {data.report.extraction.fields
                      .filter((f) => f.extraction_status !== 'not_found')
                      .map((f) => (
                        <tr key={f.key}>
                          <td className="px-5 py-2 text-ink-2">{f.label_ar}</td>
                          <td className="sp-ltr px-5 py-2 font-semibold text-ink">
                            {f.effective_value ?? '—'}{f.unit === '%' ? '%' : ` ${f.unit}`}
                          </td>
                          <td className="px-5 py-2 text-ink-3">
                            {f.source_label ?? '—'}{f.source_page ? ` (ص ${f.source_page})` : ''}
                          </td>
                          <td className="px-5 py-2">
                            <Badge tone={f.verification === 'verified' ? 'ok' : 'warn'}>
                              {f.validation_label_ar}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </Card>
            )}

            {data.report?.ai_summary && (
              <Card className="p-5">
                <p className="mb-2 text-[14px] font-bold text-ink">الملخص المولَّد</p>
                <p className="whitespace-pre-line text-[13px] leading-relaxed text-ink-2">
                  {data.report.ai_summary.text}
                </p>
                <p className="mt-3 border-t border-line pt-3 text-[11.5px] text-ink-3">
                  {data.report.ai_summary.source_label_ar}
                </p>
              </Card>
            )}
          </div>

          {/* -------------------------------------------- right column */}
          <div className="space-y-5">
            {data.report?.analysis && (
              <Card className="p-5">
                <p className="mb-2 text-[14px] font-bold text-ink">نتيجة القواعد</p>
                <Badge tone={data.report.analysis.outcome === 'review_suggested' ? 'warn' : 'ok'}>
                  {data.report.analysis.outcome_title_ar}
                </Badge>
                <ul className="mt-3 space-y-2">
                  {data.report.analysis.results.map((r) => (
                    <li key={r.rule_id} className="rounded-xl bg-surface-2 p-3">
                      <p className="sp-ltr text-[11.5px] text-ink-3">{r.rule_id} v{r.rule_version}</p>
                      <p className="mt-0.5 text-[12.5px] text-ink-2">{r.explanation_ar}</p>
                      <p className="mt-1 text-[11px] text-ink-3">{r.approval_label_ar}</p>
                    </li>
                  ))}
                </ul>
                <p className="sp-ltr mt-3 text-[11.5px] text-ink-3">
                  rules {data.report.analysis.rules_version}
                </p>
              </Card>
            )}

            {data.report?.data_quality && (
              <Card className="p-5">
                <p className="mb-2 text-[14px] font-bold text-ink">كفاية البيانات</p>
                <p className="text-[12.5px] text-ink-2">
                  الأيام: <span className="sp-ltr">{data.report.data_quality.days_of_data ?? '—'}</span> —
                  التغطية: <span className="sp-ltr">
                    {data.report.data_quality.coverage_percent ?? '—'}%
                  </span>
                </p>
                <ul className="mt-2 space-y-1">
                  {data.report.data_quality.reasons_ar.map((r) => (
                    <li key={r} className="text-[11.5px] text-ink-3">• {r}</li>
                  ))}
                </ul>
              </Card>
            )}

            <Card className="p-5">
              <p className="mb-3 text-[14px] font-bold text-ink">القرار</p>
              <label htmlFor="reviewer-note" className="mb-1.5 block text-[12.5px] text-ink-2">
                سبب القرار / ملاحظة للمريض
              </label>
              <textarea
                id="reviewer-note"
                rows={4}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="w-full resize-none rounded-xl border border-line bg-surface-2 px-3 py-2.5
                  text-[13px] leading-relaxed text-ink"
              />

              <div className="mt-4 space-y-2.5">
                {data.status === 'awaiting_review' && (
                  <Button full loading={busy}
                    onClick={() => void act(() => api.reviewerStart(id), 'بدأت المراجعة.')}>
                    بدء المراجعة
                  </Button>
                )}
                {data.status === 'under_review' && (
                  <>
                    <Button full variant="primary" loading={busy}
                      onClick={() => void act(
                        () => api.reviewerDecide(id, 'review_required', note),
                        'سُجّل القرار وأُنشئ موعد تجريبي.')}>
                      مراجعة مطلوبة — إنشاء موعد تجريبي
                    </Button>
                    <Button full variant="secondary" loading={busy}
                      onClick={() => void act(
                        () => api.reviewerDecide(id, 'data_completion', note),
                        'طُلب استكمال البيانات.')}>
                      استكمال البيانات
                    </Button>
                    <Button full variant="secondary" loading={busy}
                      onClick={() => void act(
                        () => api.reviewerDecide(id, 'no_further_action_demo', note),
                        'سُجّل القرار دون إجراء إضافي.')}>
                      لا إجراء إضافي
                    </Button>
                  </>
                )}
                {(data.status === 'reviewed' || data.status === 'more_info_requested') && (
                  <Button full variant="secondary" loading={busy} disabled={!note.trim()}
                    onClick={() => void act(() => api.reviewerNote(id, note), 'أُضيفت الملاحظة.')}>
                    إضافة ملاحظة
                  </Button>
                )}
              </div>
            </Card>

            {data.appointment && (
              <Card className="p-5">
                <p className="mb-1 text-[14px] font-bold text-ink">الموعد التجريبي</p>
                <p className="text-[12.5px] text-ink-2">{arDateTime(data.appointment.scheduled_at)}</p>
                <p className="mt-2 text-[11.5px] text-ink-3">{data.appointment.simulated_label_ar}</p>
              </Card>
            )}

            <Card className="overflow-hidden">
              <p className="border-b border-line px-5 py-3 text-[14px] font-bold text-ink">سجل الحالة</p>
              <div className="divide-y divide-line">
                {data.history.map((h, i) => (
                  <div key={`${h.at}-${i}`} className="px-5 py-2.5">
                    <p className="text-[12.5px] text-ink">
                      {h.from_label_ar ? `${h.from_label_ar} ← ${h.to_label_ar}` : h.to_label_ar}
                    </p>
                    <p className="text-[11.5px] text-ink-3">
                      {arDateTime(h.at)} — {h.actor_role === 'reviewer' ? 'مراجع' : 'مريض'}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}

      {toast && <Toast message={toast.text} tone={toast.tone} onDismiss={() => setToast(null)} />}
    </ReviewerFrame>
  );
}
