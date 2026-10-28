/** المواعيد — upcoming, past, and the follow-up status behind each one.
 *  Every appointment here is a prototype appointment and says so. */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Screen, ScreenHeader } from '../components/AppShell';
import { Icon } from '../components/Icons';
import {
  Badge, Card, EmptyState, ErrorState, ListSkeleton, Notice, Segmented,
} from '../components/ui';
import { api } from '../lib/api';
import { arDateTime, daysUntil } from '../lib/format';
import { useApi } from '../lib/useApi';
import type { Appointment } from '../lib/types';

function AppointmentCard({ a, onOpen }: { a: Appointment; onOpen: () => void }) {
  const upcoming = new Date(a.scheduled_at).getTime() >= Date.now();
  return (
    <Card as="article" className="sp-pressable cursor-pointer p-4" onClick={onOpen}>
      <div className="flex items-start gap-3">
        <span className={`grid place-items-center size-10 shrink-0 rounded-xl
          ${upcoming ? 'bg-primary-soft text-primary' : 'bg-surface-3 text-ink-3'}`}>
          <Icon name="calendar" size={20} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[14.5px] font-semibold text-ink">{a.specialty_ar}</p>
          <p className="text-[12.5px] text-ink-2">{a.clinic_label}</p>
          <p className={`mt-1 text-[12.5px] ${upcoming ? 'text-primary' : 'text-ink-3'}`}>
            {arDateTime(a.scheduled_at)}
          </p>
          {a.followup && (
            <p className="mt-1.5 text-[12px] text-ink-3">
              من الطلب <span className="sp-ltr">{a.followup.pseudo_ref}</span> — {a.followup.status_label_ar}
            </p>
          )}
        </div>
        {upcoming && <Badge tone="warn">بعد {daysUntil(a.scheduled_at)} يومًا</Badge>}
      </div>
      <p className="mt-3 border-t border-line/70 pt-2.5 text-[11.5px] text-ink-3">
        {a.simulated_label_ar}
      </p>
    </Card>
  );
}

export default function AppointmentsScreen() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<'upcoming' | 'past'>('upcoming');
  const { data, error, loading, reload } = useApi(() => api.appointments());
  const items = tab === 'upcoming' ? data?.upcoming ?? [] : data?.past ?? [];

  return (
    <Screen header={<ScreenHeader title="المواعيد" bell />}>
      <Segmented
        value={tab}
        onChange={setTab}
        options={[
          { value: 'upcoming', label: 'القادمة', badge: data?.upcoming.length },
          { value: 'past', label: 'السابقة', badge: data?.past.length },
        ]}
      />

      <div className="mt-4 space-y-3">
        {loading && <ListSkeleton rows={2} />}
        {error && <ErrorState message={error.messageAr} onRetry={reload} />}
        {data && items.length === 0 && (
          <EmptyState
            icon="calendar"
            title={tab === 'upcoming' ? 'لا توجد مواعيد قادمة' : 'لا توجد مواعيد سابقة'}
            body={tab === 'upcoming'
              ? 'يُنشئ النموذج الأولي موعدًا تجريبيًا بعد موافقة المراجع على طلب متابعة.'
              : 'ستظهر هنا المواعيد بعد انقضائها.'}
          />
        )}
        {items.map((a) => (
          <AppointmentCard key={a.id} a={a} onOpen={() => navigate(`/appointments/${a.id}`)} />
        ))}
      </div>

      {data && (
        <div className="mt-6">
          <Notice tone="warn" title="مواعيد تجريبية">{data.prototype_note_ar}</Notice>
        </div>
      )}
    </Screen>
  );
}
