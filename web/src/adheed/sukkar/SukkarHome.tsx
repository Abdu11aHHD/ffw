/** The Sukkar Plus landing screen, reached from the عضيد tile in ملفي. */

import { useNavigate } from 'react-router-dom';
import {
  Badge, Button, Card, ErrorState, ListSkeleton, Notice, SectionHeader, Skeleton,
} from '../components/ui';
import { Icon, type IconName } from '../components/Icons';
import { api } from '../lib/api';
import { arDate } from '../lib/format';
import { useApi } from '../lib/useApi';
import { JourneyArt, SukkarHeader, SukkarScreen, Timeline } from './SukkarChrome';

const SHORTCUTS: Array<{ label: string; sub: string; icon: IconName; to: string }> = [
  { label: 'تقاريري', sub: 'كل ما رفعته', icon: 'document', to: '/my-profile/diabetes-journey/reports' },
  { label: 'الاستعداد لموعدي', sub: 'ملخص وأسئلة', icon: 'clipboard', to: '/my-profile/diabetes-journey/visit-prep' },
  { label: 'طلبات المتابعة', sub: 'الحالة والقرار', icon: 'stethoscope', to: '/my-profile/diabetes-journey/followups' },
  { label: 'كيف يعمل عضيد؟', sub: 'خمس خطوات', icon: 'question', to: '/my-profile/diabetes-journey/how-it-works' },
];

export default function SukkarHome() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi(() => api.sukkarState());
  const first = data ? data.reports_total === 0 : false;

  return (
    <SukkarScreen header={<SukkarHeader title="عضيد" subtitle="رحلتك مع السكر، بطريقة أسهل" />}>
      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-[150px] w-full" />
          <Skeleton className="h-[52px] w-full" />
          <ListSkeleton rows={2} />
        </div>
      )}
      {error && <ErrorState message={error.messageAr} detail={error.detailAr} onRetry={reload} />}

      {data && (
        <div className="sp-enter space-y-6">
          {/* ------------------------------------------------ welcome */}
          <Card className="overflow-hidden">
            <div className="px-4 pt-4">
              <h2 className="text-[19px] font-bold text-ink">أهلًا بك في عضيد</h2>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-2">
                نقرأ تقرير السكر الذي ترفعه، نوضّح ما يقوله بالعربية، ونساعدك على تجهيز
                أسئلتك قبل موعدك الطبي.
              </p>
            </div>
            <JourneyArt />
          </Card>

          {/* -------------------------------------------- main action */}
          <div>
            <Button full icon="upload" onClick={() => navigate('/my-profile/diabetes-journey/upload')}>
              ابدأ بتقرير السكر
            </Button>
            <p className="mt-2 px-1 text-center text-[12px] text-ink-3">
              ملف PDF نصي مُصدَّر من تطبيق الحساس أو المضخة — حتى 15 ميغابايت.
            </p>
          </div>

          {/* ------------------------------------------ health journey */}
          <section aria-labelledby="journey-heading">
            <SectionHeader title="رحلتك الصحية" />
            <Card className="p-4">
              <div className="mb-4 flex items-start gap-2.5">
                <span className="grid place-items-center size-9 shrink-0 rounded-xl
                  bg-mint-soft text-mint">
                  <Icon name="spark" size={18} />
                </span>
                <div className="min-w-0 flex-1">
                  <p id="journey-heading" className="text-[14.5px] font-bold text-ink">
                    {data.journey.title_ar}
                  </p>
                  <p className="mt-0.5 text-[13px] leading-relaxed text-ink-2">
                    {data.journey.body_ar}
                  </p>
                </div>
              </div>
              <Timeline steps={data.journey.steps} activeLabel="الخطوة الحالية" />
            </Card>
          </section>

          {/* ---------------------------------- first-use or reports */}
          {first ? (
            <Notice tone="mint" icon="glucose" title="خلّنا نرتّب تقريرك مع بعض">
              لم ترفع تقريرًا بعد، فلا توجد أرقام نعرضها. ارفع أول تقرير وسنقرأ المؤشرات
              المطبوعة فيه ونحتفظ بمصدر كل قيمة.
            </Notice>
          ) : (
            <section aria-labelledby="recent-reports">
              <SectionHeader
                title="آخر التقارير"
                actionLabel="عرض الكل"
                onAction={() => navigate('/my-profile/diabetes-journey/reports')}
              />
              <div className="space-y-3">
                {data.recent_reports.slice(0, 3).map((r) => (
                  <Card
                    key={r.id}
                    className="sp-pressable cursor-pointer p-3.5"
                    onClick={() => navigate(`/my-profile/diabetes-journey/reports/${r.id}`)}
                  >
                    <div className="flex items-center gap-3">
                      <span className="grid place-items-center size-9 shrink-0 rounded-xl
                        bg-primary-soft text-primary">
                        <Icon name="document" size={18} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13.5px] font-semibold text-ink">
                          {r.outcome_title_ar ?? r.status_label_ar}
                        </p>
                        <p className="text-[12px] text-ink-3">{arDate(r.created_at)}</p>
                      </div>
                      <Badge tone={r.status === 'failed' ? 'danger'
                        : r.status === 'needs_review' ? 'warn' : 'ok'}>
                        {r.status_label_ar}
                      </Badge>
                    </div>
                  </Card>
                ))}
              </div>
            </section>
          )}

          {/* ---------------------------------------------- shortcuts */}
          <section aria-labelledby="shortcuts-heading">
            <SectionHeader title="اختصارات" />
            <div className="grid grid-cols-2 gap-3">
              {SHORTCUTS.map((s) => (
                <button
                  key={s.to}
                  type="button"
                  onClick={() => navigate(s.to)}
                  className="sp-pressable rounded-tile border border-line/70 bg-surface p-3.5 text-right"
                >
                  <span className="mb-2 grid place-items-center size-9 rounded-xl
                    bg-mint-soft text-mint">
                    <Icon name={s.icon} size={18} />
                  </span>
                  <span className="block text-[13.5px] font-semibold text-ink">{s.label}</span>
                  <span className="block text-[11.5px] text-ink-3">{s.sub}</span>
                </button>
              ))}
            </div>
          </section>

          <Notice tone="neutral" title="حدود الخدمة">
            <ul className="list-disc space-y-1 pr-4">
              {data.limits_ar.map((l) => <li key={l}>{l}</li>)}
            </ul>
          </Notice>
        </div>
      )}
    </SukkarScreen>
  );
}
