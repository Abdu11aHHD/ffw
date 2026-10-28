import { useParams } from 'react-router-dom';
import { ScreenHeader } from '../components/AppShell';
import { Card, ErrorState, Skeleton } from '../components/ui';
import { api } from '../lib/api';
import { arDateTime } from '../lib/format';
import { useApi } from '../lib/useApi';

export default function NotificationDetailScreen() {
  const { id = '' } = useParams();
  const { data, error, loading, reload } = useApi(() => api.notifications(), [id]);
  const item = data?.items.find((n) => n.id === id) ?? null;

  return (
    <>
      <ScreenHeader title="تفاصيل التنبيه" back />
      <main className="sp-scroll px-4 pt-4">
        {loading && <Skeleton className="h-40 w-full" />}
        {error && <ErrorState message={error.messageAr} onRetry={reload} />}
        {data && !item && <ErrorState message="لم نعثر على هذا التنبيه." />}
        {item && (
          <Card className="sp-enter p-4">
            <p className="text-[12.5px] text-ink-3">{arDateTime(item.created_at)}</p>
            <h2 className="mt-1 text-[17px] font-bold text-primary">{item.title_ar}</h2>
            <p className="mt-3 text-[14px] leading-relaxed text-ink-2">{item.body_ar}</p>
            <p className="mt-4 border-t border-line/70 pt-3 text-[12px] text-ink-3">
              المرسل: {item.sender_ar}
            </p>
          </Card>
        )}
      </main>
    </>
  );
}
