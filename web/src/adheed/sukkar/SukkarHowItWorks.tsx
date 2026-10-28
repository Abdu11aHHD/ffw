import { useNavigate } from 'react-router-dom';
import { Button, Card, ErrorState, ListSkeleton, Notice, SectionHeader } from '../components/ui';
import { api } from '../lib/api';
import { useApi } from '../lib/useApi';
import { JourneyArt, SukkarHeader, SukkarScreen } from './SukkarChrome';

export default function SukkarHowItWorks() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi(() => api.sukkarState());

  return (
    <SukkarScreen header={<SukkarHeader title="كيف يعمل عضيد؟" subtitle="خمس خطوات واضحة" />}>
      {loading && <ListSkeleton rows={3} />}
      {error && <ErrorState message={error.messageAr} onRetry={reload} />}

      {data && (
        <div className="sp-enter space-y-6">
          <Card className="overflow-hidden">
            <div className="px-4 pt-4">
              <p className="text-[13.5px] leading-relaxed text-ink-2">
                عضيد يقرأ ما هو <span className="font-semibold text-ink">مطبوع</span> في تقريرك،
                ولا يخترع أي رقم. كل قيمة تظهر مع مصدرها والصفحة التي جاءت منها.
              </p>
            </div>
            <JourneyArt />
          </Card>

          <section>
            <SectionHeader title="الخطوات" />
            <div className="space-y-3">
              {data.how_it_works.map((s) => (
                <Card key={s.step} className="p-4">
                  <div className="flex gap-3">
                    <span className="sp-ltr grid size-8 shrink-0 place-items-center rounded-xl
                      bg-mint-soft text-[13px] font-bold text-mint">{s.step}</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[14px] font-semibold text-ink">{s.title_ar}</p>
                      <p className="mt-0.5 text-[12.5px] leading-relaxed text-ink-2">{s.body_ar}</p>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </section>

          <Notice tone="warn" title="ما لا يفعله عضيد">
            <ul className="list-disc space-y-1 pr-4">
              {data.limits_ar.map((l) => <li key={l}>{l}</li>)}
              <li>لا يحدد ما إذا كانت حالتك طارئة. للحالات العاجلة اتصل بالطوارئ (997 / 911).</li>
            </ul>
          </Notice>

          <Button full icon="upload" onClick={() => navigate('/my-profile/diabetes-journey/upload')}>
            ابدأ بتقرير السكر
          </Button>
        </div>
      )}
    </SukkarScreen>
  );
}
