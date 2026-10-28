/** Reuses the team's outer shell; never adds another navigation bar. */
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { BellIcon, ChevronRight } from './Icons';
export function BottomNav() { return null; }
export function ScreenHeader({title, back, onBack, action, subtitle, bell}: {
  title: string; back?: boolean; onBack?: () => void; action?: ReactNode; subtitle?: string; bell?: boolean;
}) {
  const navigate = useNavigate();
  return <header className="adh-header border-b border-line px-4 py-4">
    <div className="flex items-center gap-3">
      {back && <button type="button" aria-label="رجوع" onClick={() => onBack ? onBack() : navigate(-1)} className="grid size-10 place-items-center rounded-xl"><ChevronRight /></button>}
      <div className="flex-1"><h1 className="text-[22px] font-bold text-ink">{title}</h1>{subtitle && <p className="text-[13px] text-ink-2">{subtitle}</p>}</div>
      {bell && <button type="button" aria-label="التنبيهات" onClick={() => navigate('/notifications')} className="grid size-10 place-items-center rounded-xl"><BellIcon /></button>}{action}
    </div>
  </header>;
}
export function Screen({header,children,className=''}: {header?: ReactNode; children: ReactNode; className?: string}) {
  return <>{header}<div className={`sp-scroll px-4 pt-4 ${className}`}>{children}</div></>;
}
