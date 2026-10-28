/** تقاريري — the report history. */

import { useNavigate } from 'react-router-dom';
import { Badge, Button, Card, EmptyState, ErrorState, ListSkeleton } from '../components/ui';
import { Icon } from '../components/Icons';
import { api } from '../lib/api';
import { arDate, arPeriod, formatFileSize } from '../lib/format';
import { useApi } from '../lib/useApi';
import { SukkarHeader, SukkarScreen } from './SukkarChrome';

const TONE = { failed: 'danger', needs_review: 'warn', processing: 'info', ready: 'ok' } as const;

export default function SukkarReports() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi(() => api.reports(50, 0));

  return (
    <SukkarScreen header={<SukkarHeader title="تقاريري" subtitle="كل ما رفعته في عضيد" />}>
      {loading && <ListSkeleton rows={3} />}
      {error && <ErrorState message={error.messageAr} onRetry={reload} />}

      {data && data.items.length === 0 && (
        <EmptyState
          icon="document"
          title="لم ترفع تقريرًا بعد"
          body="ارفع أول تقرير سكر وسنقرأ المؤشرات المطبوعة فيه ونعرضها مع مصدر كل قيمة."
          action={<Button icon="upload" onClick={() => navigate('/my-profile/diabetes-journey/upload')}>ابدأ بتقرير السكر</Button>}
        />
      )}

      {data && data.items.length > 0 && (
        <div className="sp-enter space-y-3">
          {data.items.map((r) => (
            <Card
              key={r.id}
              as="article"
              className="sp-pressable cursor-pointer p-4"
              onClick={() => navigate(`/my-profile/diabetes-journey/reports/${r.id}`)}
            >
              <div className="flex items-start gap-3">
                <span className="grid place-items-center size-10 shrink-0 rounded-xl
                  bg-primary-soft text-primary">
                  <Icon name="document" size={19} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold text-ink">
                    {r.outcome_title_ar ?? r.status_label_ar}
                  </p>
                  <p className="mt-0.5 text-[12.5px] text-ink-2">
                    {r.period?.start
                      ? arPeriod(r.period.start, r.period.end)
                      : 'لم تُحدَّد فترة في التقرير'}
                  </p>
                  <p className="mt-0.5 text-[11.5px] text-ink-3">
                    رُفع {arDate(r.created_at)} — {formatFileSize(r.file_size_bytes)}
                  </p>
                  <p className="mt-1 truncate text-[12px] text-ink-3" dir="auto">{r.file_name}</p>
                </div>
                <Badge tone={TONE[r.status] ?? 'neutral'}>{r.status_label_ar}</Badge>
              </div>
              {r.error_ar && (
                <p className="mt-3 border-t border-line/70 pt-2.5 text-[12.5px] text-danger">
                  {r.error_ar}
                </p>
              )}
            </Card>
          ))}
          <Button full variant="secondary" icon="upload" onClick={() => navigate('/my-profile/diabetes-journey/upload')}>
            رفع تقرير جديد
          </Button>
        </div>
      )}
    </SukkarScreen>
  );
}
