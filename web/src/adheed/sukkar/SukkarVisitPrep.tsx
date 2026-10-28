/** الاستعداد لموعدي — the appointment-preparation summary. */

import { useNavigate, useParams } from 'react-router-dom';
import { Badge, Button, Card, EmptyState, ErrorState, ListSkeleton, Notice, SectionHeader }
  from '../components/ui';
import { Icon } from '../components/Icons';
import { api } from '../lib/api';
import { useApi } from '../lib/useApi';
import { SukkarHeader, SukkarScreen } from './SukkarChrome';

export default function SukkarVisitPrep() {
  const { reportId } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi(() => api.visitPrep(reportId), [reportId]);

  return (
    <SukkarScreen
      header={<SukkarHeader title="الاستعداد لموعدي" subtitle="كل معلومة تساعدك تستعد لموعدك" />}
    >
      {loading && <ListSkeleton rows={3} />}
      {error && <ErrorState message={error.messageAr} onRetry={reload} />}

      {data && !data.report_id && (
        <EmptyState
          icon="clipboard"
          title="لا يوجد تقرير لتجهيز الملخص منه"
          body="ارفع تقرير سكر أولًا، ثم سنجمع لك المؤشرات المتاحة وحدود البيانات والأسئلة المقترحة."
          action={<Button icon="upload" onClick={() => navigate('/my-profile/diabetes-journey/upload')}>ابدأ بتقرير السكر</Button>}
        />
      )}

      {data && data.report_id && (
        <div className="sp-enter space-y-6">
          <Card className="p-4">
            <div className="flex items-start gap-3">
              <span className="grid place-items-center size-10 shrink-0 rounded-xl
                bg-mint-soft text-mint">
                <Icon name="clipboard" size={20} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[14.5px] font-bold text-ink">ملخص لموعدك</p>
                <p className="mt-0.5 text-[12.5px] text-ink-2">
                  الفترة: {data.period_ar ?? 'غير محددة'}
                  {data.period_days ? <> — <span className="sp-ltr">{data.period_days}</span> يومًا</> : null}
                </p>
              </div>
            </div>
            {data.outcome && (
              <div className="mt-3 border-t border-line/70 pt-3">
                <Badge tone={data.outcome.outcome === 'routine_summary' ? 'ok'
                  : data.outcome.outcome === 'review_suggested' ? 'warn' : 'info'}>
                  {data.outcome.outcome_title_ar}
                </Badge>
              </div>
            )}
          </Card>

          {/* ------------------------------------------ metrics */}
          <section>
            <SectionHeader title="المؤشرات المتاحة" />
            <Card className="divide-y divide-line/70 overflow-hidden">
              {data.metrics.map((m) => (
                <div key={m.label_ar} className="px-4 py-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="text-[13.5px] text-ink-2">{m.label_ar}</p>
                    <p className={`sp-ltr text-[14px] font-bold
                      ${m.value_ar === 'غير متاح' ? 'text-ink-3' : 'text-ink'}`}>
                      {m.value_ar}
                    </p>
                  </div>
                  {m.source_ar && <p className="mt-0.5 text-[11.5px] text-ink-3">المصدر: {m.source_ar}</p>}
                  {m.note_ar && <p className="text-[11.5px] text-ink-3">{m.note_ar}</p>}
                </div>
              ))}
            </Card>
          </section>

          {/* ---------------------------------------- patterns */}
          {data.patterns_ar.length > 0 && (
            <section>
              <SectionHeader title="أنماط ملاحظة" />
              <Card className="p-4">
                <ul className="space-y-2">
                  {data.patterns_ar.map((p) => (
                    <li key={p} className="flex gap-2 text-[13px] leading-relaxed text-ink-2">
                      <span className="mt-2 size-1.5 shrink-0 rounded-full bg-warn" />
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          )}

          {/* ------------------------------------- comparison */}
          <section>
            <SectionHeader title="المقارنة مع تقرير سابق" />
            {data.comparison?.comparable ? (
              <Card className="p-4">
                <p className="mb-3 text-[12.5px] text-ink-3">
                  {data.comparison.previous_period_ar} ← {data.comparison.current_period_ar}
                </p>
                <ul className="space-y-2">
                  {data.comparison.deltas.map((d) => (
                    <li key={d.key} className="flex items-baseline justify-between gap-3 text-[13px]">
                      <span className="text-ink-2">{d.label_ar}</span>
                      <span className={`sp-ltr font-semibold
                        ${d.delta > 0 ? 'text-mint' : d.delta < 0 ? 'text-warn' : 'text-ink'}`}>
                        {d.delta_text_ar}
                      </span>
                    </li>
                  ))}
                </ul>
                {data.comparison.caveats_ar.length > 0 && (
                  <ul className="mt-3 space-y-1 border-t border-line/70 pt-2.5">
                    {data.comparison.caveats_ar.map((c) => (
                      <li key={c} className="text-[11.5px] text-ink-3">• {c}</li>
                    ))}
                  </ul>
                )}
              </Card>
            ) : (
              <Notice tone="neutral" title="المقارنة غير متاحة">
                {data.comparison?.reason_ar ?? 'لا توجد تقارير كافية للمقارنة.'}
              </Notice>
            )}
          </section>

          {/* ------------------------------------- limitations */}
          {(data.limitations_ar.length > 0 || data.missing_ar.length > 0) && (
            <section>
              <SectionHeader title="حدود البيانات" />
              <div className="space-y-3">
                {data.limitations_ar.length > 0 && (
                  <Notice tone="warn" title="ما يجب الانتباه له">
                    <ul className="list-disc space-y-1 pr-4">
                      {data.limitations_ar.map((l) => <li key={l}>{l}</li>)}
                    </ul>
                  </Notice>
                )}
                {data.missing_ar.length > 0 && (
                  <Notice tone="neutral" title="معلومات ناقصة">
                    <ul className="list-disc space-y-1 pr-4">
                      {data.missing_ar.slice(0, 8).map((m) => <li key={m}>{m}</li>)}
                    </ul>
                  </Notice>
                )}
              </div>
            </section>
          )}

          {/* --------------------------------------- questions */}
          <section>
            <SectionHeader title="أسئلة مقترحة لفريقك الصحي" />
            <Card className="divide-y divide-line/70 overflow-hidden">
              {data.questions_ar.map((q, i) => (
                <div key={q} className="flex items-start gap-3 px-4 py-3">
                  <span className="sp-ltr mt-0.5 grid size-6 shrink-0 place-items-center rounded-full
                    bg-mint-soft text-[11px] font-bold text-mint">{i + 1}</span>
                  <p className="text-[13px] leading-relaxed text-ink-2">{q}</p>
                </div>
              ))}
            </Card>
          </section>

          {data.target_notes_ar.length > 0 && (
            <Notice tone="neutral" title="عن الأهداف المرجعية">
              <ul className="list-disc space-y-1 pr-4">
                {data.target_notes_ar.map((n) => <li key={n}>{n}</li>)}
              </ul>
            </Notice>
          )}

          <Notice tone="neutral" title="تنويه">{data.disclaimer_ar}</Notice>

          <Button full variant="secondary" icon="stethoscope"
            onClick={() => navigate(`/my-profile/diabetes-journey/followups/new?report=${data.report_id}`)}>
            طلب مراجعة مختص
          </Button>
        </div>
      )}
    </SukkarScreen>
  );
}
