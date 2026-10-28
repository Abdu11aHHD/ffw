import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { dailyActivity, patients } from '../data/mockData';
import { api } from '../adheed/lib/api';
import { useSession } from '../adheed/lib/session';
import type { Appointment, NotificationItem, PatientProfile } from '../types';

/**
 * In-memory frontend state for the mockup (resets on refresh — only the language is persisted).
 * No network calls are made anywhere in this app.
 */
interface AppStateValue {
  appointments: Appointment[];
  addAppointment: (a: Omit<Appointment, 'id' | 'status'>) => void;
  cancelAppointment: (id: string) => void;
  notifications: NotificationItem[];
  unreadCount: number;
  markAllRead: () => void;
  markRead: (id: string) => void;
  activeProfile: PatientProfile;
  setActiveProfileId: (id: string) => void;
  stepTarget: number;
  setStepTarget: (n: number) => void;
  toast: string | null;
  showToast: (message: string) => void;
}

const AppStateContext = createContext<AppStateValue | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const {profile} = useSession();
  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      if (profile?.role !== 'patient') {setAppointments([]); setNotifications([]); return;}
      try {
        const [a,n] = await Promise.all([api.appointments(),api.notifications()]);
        if (cancelled) return;
        setAppointments([...a.upcoming,...a.past].map(x => ({
          id:x.id,clinic:{ar:x.specialty_ar,en:x.specialty_ar},facility:{ar:x.clinic_label,en:x.clinic_label},
          dateTime:x.scheduled_at,status:x.status === 'upcoming' ? 'upcoming' : 'previous',visitType:'inPerson',
        })));
        setNotifications(n.items.map(x => ({id:x.id,title:{ar:x.title_ar,en:x.title_ar},body:{ar:x.body_ar,en:x.body_ar},createdAt:x.created_at,read:x.read,kind:'general'})));
      } catch { /* Connected screens show actionable errors; never substitute sample appointments. */ }
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(),15000);
    window.addEventListener('focus',refresh);
    return () => {cancelled=true; window.clearInterval(timer); window.removeEventListener('focus',refresh);};
  },[profile]);
  const [activeProfileId, setActiveProfileId] = useState(patients[0].id);
  const [stepTarget, setStepTarget] = useState(dailyActivity.defaultTarget);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number | undefined>(undefined);

  const showToast = useCallback((message: string) => {
    setToast(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2600);
  }, []);

  const value = useMemo<AppStateValue>(
    () => ({
      appointments,
      addAppointment: (a) =>
        setAppointments((cur) =>
          [...cur, { ...a, id: `apt-${Date.now()}`, status: 'upcoming' as const }].sort((x, y) =>
            x.dateTime.localeCompare(y.dateTime),
          ),
        ),
      cancelAppointment: (id) => setAppointments((cur) => cur.filter((a) => a.id !== id)),
      notifications,
      unreadCount: notifications.filter((n) => !n.read).length,
      markAllRead: () => setNotifications((cur) => cur.map((n) => ({ ...n, read: true }))),
      markRead: (id) => setNotifications((cur) => cur.map((n) => (n.id === id ? { ...n, read: true } : n))),
      activeProfile: patients.find((p) => p.id === activeProfileId) ?? patients[0],
      setActiveProfileId,
      stepTarget,
      setStepTarget,
      toast,
      showToast,
    }),
    [appointments, notifications, activeProfileId, stepTarget, toast, showToast],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppStateValue {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error('useAppState must be used inside <AppStateProvider>');
  return ctx;
}
