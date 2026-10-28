/** Shared chrome for the Sukkar Plus service: a warmer header that still
 *  belongs to the same application shell, plus the journey timeline. */

import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, Icon } from '../components/Icons';
import { BottomNav } from '../components/AppShell';
import type { JourneyStep } from '../lib/types';

export function SukkarHeader({ title, subtitle, back = true, action }: {
  title: string; subtitle?: string; back?: boolean; action?: ReactNode;
}) {
  const navigate = useNavigate();
  return (
    <header className="sp-safe-top sticky top-0 z-20 border-b border-line/50
      bg-bg/95 backdrop-blur-md">
      <div className="flex items-center gap-2.5 px-4 py-3.5">
        {back && (
          <button
            type="button"
            onClick={() => navigate(-1)}
            aria-label="رجوع"
            className="sp-pressable -mr-1.5 grid place-items-center size-9 rounded-xl text-ink"
          >
            <ChevronRight size={22} />
          </button>
        )}
        <span className="grid place-items-center size-8 shrink-0 rounded-lg bg-mint-soft text-mint">
          <Icon name="glucose" size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[18px] font-bold leading-tight text-ink">{title}</h1>
          {subtitle && <p className="truncate text-[12px] text-ink-3">{subtitle}</p>}
        </div>
        {action}
      </div>
    </header>
  );
}

export function SukkarScreen({ header, children }: { header: ReactNode; children: ReactNode }) {
  return (
    <>
      {header}
      <main className="sp-scroll px-4 pt-4">{children}</main>
      <BottomNav />
    </>
  );
}

/** A small, calm illustration of a glucose journey. Decorative only. */
export function JourneyArt() {
  return (
    <svg viewBox="0 0 320 96" className="h-[88px] w-full" role="presentation" aria-hidden>
      <defs>
        <linearGradient id="sp-j" x1="1" y1="0" x2="0" y2="0">
          <stop offset="0%" stopColor="#1e8fe0" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#32d4b4" stopOpacity="0.9" />
        </linearGradient>
        <linearGradient id="sp-f" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1e8fe0" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#1e8fe0" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect x="0" y="34" width="320" height="30" rx="8" fill="#1e8fe0" opacity="0.07" />
      <path d="M8 70 C 48 70, 56 30, 96 34 S 150 72, 186 54 S 250 22, 312 30"
        fill="none" stroke="url(#sp-j)" strokeWidth="3" strokeLinecap="round" />
      <path d="M8 70 C 48 70, 56 30, 96 34 S 150 72, 186 54 S 250 22, 312 30 L 312 96 L 8 96 Z"
        fill="url(#sp-f)" />
      <circle cx="312" cy="30" r="5" fill="#32d4b4" />
      <circle cx="186" cy="54" r="3.5" fill="#1e8fe0" />
      <circle cx="96" cy="34" r="3.5" fill="#1e8fe0" />
    </svg>
  );
}

/** Step-based timeline showing the real workflow state. */
export function Timeline({ steps, activeLabel }: { steps: JourneyStep[]; activeLabel?: string }) {
  const firstPending = steps.findIndex((s) => !s.done);
  return (
    <ol className="relative space-y-0">
      {steps.map((s, i) => {
        const current = i === firstPending;
        const last = i === steps.length - 1;
        return (
          <li key={s.key} className="relative flex gap-3 pb-4 last:pb-0">
            {!last && (
              <span
                aria-hidden
                className={`absolute right-[13px] top-7 bottom-0 w-px
                  ${s.done ? 'bg-mint/50' : 'bg-line'}`}
              />
            )}
            <span
              className={`relative z-10 grid size-7 shrink-0 place-items-center rounded-full border
                ${s.done ? 'border-mint bg-mint text-[#042019]'
                  : current ? 'border-primary bg-primary-soft text-primary'
                    : 'border-line bg-surface-2 text-ink-3'}`}
            >
              {s.done
                ? <Icon name="check" size={15} />
                : <span className="sp-ltr text-[11px] font-bold">{i + 1}</span>}
            </span>
            <span className="min-w-0 flex-1 pt-0.5">
              <span className={`block text-[13.5px] font-medium
                ${s.done ? 'text-ink' : current ? 'text-primary' : 'text-ink-3'}`}>
                {s.label_ar}
              </span>
              {current && activeLabel && (
                <span className="mt-0.5 block text-[12px] text-ink-2">{activeLabel}</span>
              )}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
