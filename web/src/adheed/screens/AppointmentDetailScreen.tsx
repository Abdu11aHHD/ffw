import { useNavigate, useParams } from 'react-router-dom';
import { ScreenHeader } from '../components/AppShell';
import { Icon } from '../components/Icons';
import { Badge, Button, Card, ErrorState, ListSkeleton, Notice, SectionHeader } from '../components/ui';
import { api } from '../lib/api';
import { arDateTime } from '../lib/format';
import { useApi } from '../lib/useApi';

export default function AppointmentDetailScreen() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi(() => api.appointment(id), [id]);

  return (
    <>
      <ScreenHeader title="تفاصيل الموعد" back />
      <main className="sp-scroll px-4 pt-4">
        {loading && <ListSkeleton rows={2} />}
        {error && <ErrorState message={error.messageAr} onRetry={reload} />}

        {data && (
          <div className="sp-enter space-y-5">
            <Card className="p-4">
              <div className="flex items-start gap-3">
                <span className="grid place-items-center size-11 shrink-0 rounded-xl
                  bg-primary-soft text-primary">
                  <Icon name="calendar" size={22} />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-[16px] font-bold text-ink">{data.specialty_ar}</h2>
                  <p className="text-[13px] text-ink-2">{data.clinic_label}</p>
                  <p className="mt-1.5 text-[13px] text-primary">{arDateTime(data.scheduled_at)}</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 border-t border-line/70 pt-3">
                <Badge tone="warn" icon="alert">موعد تجريبي</Badge>
                {data.followup && (
                  <Badge tone="info">الطلب {data.followup.pseudo_ref}</Badge>
                )}
              </div>
            </Card>

            <Notice tone="warn" title="لم يُحجز موعد حقيقي">
              {data.prototype_note_ar}
            </Notice>

            {data.preparation && (
              <section>
                <SectionHeader title="الاستعداد لهذا الموعد" />
                <Card className="p-4 space-y-3">
                  <p className="text-[13px] text-ink-2">
                    الفترة: {data.preparation.period_ar ?? 'غير محددة'}
                  </p>
                  {data.preparation.questions_ar.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-[13.5px] font-semibold text-ink">أسئلة مقترحة</p>
                      <ul className="space-y-1.5">
                        {data.preparation.questions_ar.slice(0, 3).map((q) => (
                          <li key={q} className="flex gap-2 text-[13px] text-ink-2">
                            <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-mint" />
                            <span>{q}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <Button full variant="secondary"
                    onClick={() => navigate(`/my-profile/diabetes-journey/visit-prep${data.report_id ? `/${data.report_id}` : ''}`)}>
                    فتح الملخص الكامل
                  </Button>
                </Card>
              </section>
            )}

            {data.followup_id && (
              <Button full variant="ghost" onClick={() => navigate(`/my-profile/diabetes-journey/followups/${data.followup_id}`)}>
                عرض طلب المتابعة المرتبط
              </Button>
            )}
          </div>
        )}
      </main>
    </>
  );
}
