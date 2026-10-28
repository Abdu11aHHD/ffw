/** Shared building blocks: cards, buttons, badges, states, dialogs. */

import { useEffect, useRef, type ReactNode } from 'react';
import { AlertIcon, CheckCircle, ChevronLeft, CloseIcon, Icon, InfoIcon, RefreshIcon,
  type IconName } from './Icons';

/* ------------------------------------------------------------------ card */

export function Card({ children, className = '', as: As = 'div', ...rest }: {
  children: ReactNode; className?: string; as?: 'div' | 'section' | 'article';
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <As className={`rounded-card bg-surface border border-line/70 ${className}`}
      {...(rest.onClick ? {role:'button', tabIndex:0, onKeyDown:(e: React.KeyboardEvent<HTMLElement>) => {
        if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); e.currentTarget.click();}
      }} : {})} {...rest}>
      {children}
    </As>
  );
}

export function SectionHeader({ title, actionLabel, onAction, className = '' }: {
  title: string; actionLabel?: string; onAction?: () => void; className?: string;
}) {
  return (
    <div className={`flex items-center justify-between gap-3 px-1 mb-3 ${className}`}>
      <h2 className="text-[17px] font-bold text-ink">{title}</h2>
      {actionLabel && (
        <button type="button" onClick={onAction}
          className="text-[13px] font-medium text-primary hover:text-primary-strong">
          {actionLabel}
        </button>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- button */

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'mint';

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-strong active:bg-primary-strong',
  mint: 'bg-mint text-[#042019] hover:brightness-110',
  secondary: 'bg-surface-3 text-ink border border-line hover:bg-[#2e333b]',
  ghost: 'bg-transparent text-primary hover:bg-primary-soft',
  danger: 'bg-danger-soft text-danger border border-danger/40 hover:bg-danger/20',
};

export function Button({
  children, variant = 'primary', icon, loading = false, full = false,
  className = '', disabled, ...rest
}: {
  children: ReactNode; variant?: Variant; icon?: IconName; loading?: boolean; full?: boolean;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={`sp-pressable inline-flex items-center justify-center gap-2 rounded-pill
        px-5 min-h-[46px] text-[15px] font-semibold
        disabled:opacity-50 disabled:cursor-not-allowed
        ${VARIANTS[variant]} ${full ? 'w-full' : ''} ${className}`}
      {...rest}
    >
      {loading ? <Spinner /> : icon ? <Icon name={icon} size={19} /> : null}
      <span>{children}</span>
    </button>
  );
}

export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <span
      role="status"
      aria-label="جارٍ التحميل"
      style={{ width: size, height: size }}
      className="inline-block rounded-full border-2 border-current border-t-transparent animate-spin"
    />
  );
}

/* ----------------------------------------------------------------- badge */

export type Tone = 'neutral' | 'info' | 'ok' | 'warn' | 'danger' | 'mint';

const TONES: Record<Tone, string> = {
  neutral: 'bg-surface-3 text-ink-2 border-line',
  info: 'bg-primary-soft text-primary border-primary/35',
  ok: 'bg-ok-soft text-ok border-ok/35',
  warn: 'bg-warn-soft text-warn border-warn/35',
  danger: 'bg-danger-soft text-danger border-danger/35',
  mint: 'bg-mint-soft text-mint border-mint/35',
};

export function Badge({ children, tone = 'neutral', icon }: {
  children: ReactNode; tone?: Tone; icon?: IconName;
}) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-pill border
      px-2.5 py-1 text-[12px] font-medium leading-none ${TONES[tone]}`}>
      {icon && <Icon name={icon} size={13} />}
      {children}
    </span>
  );
}

/* ---------------------------------------------------------------- states */

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`sp-skeleton rounded-xl ${className}`} aria-hidden />;
}

export function ListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="جارٍ التحميل">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-[92px] w-full" />
      ))}
      <span className="sr-only">جارٍ التحميل…</span>
    </div>
  );
}

export function EmptyState({ icon = 'info', title, body, action }: {
  icon?: IconName; title: string; body?: string; action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center text-center gap-3 py-10 px-5">
      <div className="grid place-items-center size-14 rounded-2xl bg-primary-soft text-primary">
        <Icon name={icon} size={26} />
      </div>
      <h3 className="text-[16px] font-bold text-ink">{title}</h3>
      {body && <p className="text-[13.5px] text-ink-2 max-w-[300px] leading-relaxed">{body}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, detail, onRetry }: {
  message: string; detail?: string | null; onRetry?: () => void;
}) {
  return (
    <Card className="p-5 text-center border-danger/30" role="alert">
      <div className="mx-auto mb-3 grid place-items-center size-12 rounded-2xl bg-danger-soft text-danger">
        <AlertIcon size={24} />
      </div>
      <p className="text-[14.5px] font-semibold text-ink">{message}</p>
      {detail && <p className="mt-1.5 text-[13px] text-ink-2">{detail}</p>}
      {onRetry && (
        <div className="mt-4">
          <Button variant="secondary" onClick={onRetry} icon="info">إعادة المحاولة</Button>
        </div>
      )}
    </Card>
  );
}

export function Notice({ tone = 'info', title, children, icon }: {
  tone?: Tone; title?: string; children: ReactNode; icon?: IconName;
}) {
  const ring = {
    neutral: 'border-line bg-surface-2', info: 'border-primary/30 bg-primary-soft',
    ok: 'border-ok/30 bg-ok-soft', warn: 'border-warn/30 bg-warn-soft',
    danger: 'border-danger/35 bg-danger-soft', mint: 'border-mint/30 bg-mint-soft',
  }[tone];
  const text = {
    neutral: 'text-ink-2', info: 'text-primary', ok: 'text-ok',
    warn: 'text-warn', danger: 'text-danger', mint: 'text-mint',
  }[tone];
  return (
    <div className={`rounded-card border p-3.5 ${ring}`}>
      <div className="flex gap-2.5">
        <span className={`shrink-0 mt-0.5 ${text}`}>
          {icon ? <Icon name={icon} size={18} /> : tone === 'warn' || tone === 'danger'
            ? <AlertIcon size={18} /> : <InfoIcon size={18} />}
        </span>
        <div className="min-w-0 flex-1">
          {title && <p className={`text-[13.5px] font-bold mb-1 ${text}`}>{title}</p>}
          <div className="text-[13px] leading-relaxed text-ink-2">{children}</div>
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- rows */

export function ListRow({ icon, label, sublabel, onClick, trailing, danger = false }: {
  icon?: IconName; label: string; sublabel?: string; onClick?: () => void;
  trailing?: ReactNode; danger?: boolean;
}) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={`sp-list-row sp-pressable w-full flex items-center gap-3 px-4 py-3.5 text-right
        ${onClick ? 'cursor-pointer' : ''}`}
    >
      {icon && (
        <span className={`grid place-items-center size-9 shrink-0 rounded-xl
          ${danger ? 'bg-danger-soft text-danger' : 'bg-primary-soft text-primary'}`}>
          <Icon name={icon} size={19} />
        </span>
      )}
      <span className="flex-1 min-w-0">
        <span className="block text-[14.5px] font-medium text-ink truncate">{label}</span>
        {sublabel && <span className="block text-[12.5px] text-ink-3 truncate">{sublabel}</span>}
      </span>
      {trailing ?? (onClick ? <ChevronLeft size={18} className="text-ink-3 shrink-0" /> : null)}
    </Tag>
  );
}

export function RowGroup({ children }: { children: ReactNode }) {
  return (
    <Card className="overflow-hidden divide-y divide-line/70">{children}</Card>
  );
}

/* --------------------------------------------------------------- dialog */

export function ConfirmDialog({
  open, title, body, confirmLabel = 'تأكيد', cancelLabel = 'إلغاء',
  tone = 'primary', onConfirm, onCancel, busy = false,
}: {
  open: boolean; title: string; body: string; confirmLabel?: string; cancelLabel?: string;
  tone?: Variant; onConfirm: () => void; onCancel: () => void; busy?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onCancel]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 px-6"
      role="dialog" aria-modal="true" aria-label={title} onClick={onCancel}>
      <div
        ref={ref}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="sp-enter w-full max-w-[360px] rounded-card bg-surface border border-line p-5 outline-none"
      >
        <h3 className="text-[16px] font-bold text-ink mb-2">{title}</h3>
        <p className="text-[13.5px] text-ink-2 leading-relaxed mb-5">{body}</p>
        <div className="flex gap-2.5">
          <Button variant={tone} onClick={onConfirm} loading={busy} className="flex-1">
            {confirmLabel}
          </Button>
          <Button variant="secondary" onClick={onCancel} className="flex-1">{cancelLabel}</Button>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- toast */

export function Toast({ message, tone = 'ok', onDismiss }: {
  message: string; tone?: 'ok' | 'danger'; onDismiss: () => void;
}) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 4200);
    return () => clearTimeout(t);
  }, [onDismiss]);
  return (
    <div
      role="status"
      className={`sp-enter fixed inset-x-0 bottom-[calc(var(--sp-nav-h)+16px)] z-50 mx-auto
        w-[min(92%,400px)] rounded-card border px-4 py-3 flex items-center gap-2.5
        ${tone === 'ok' ? 'bg-ok-soft border-ok/40 text-ok' : 'bg-danger-soft border-danger/40 text-danger'}`}
    >
      {tone === 'ok' ? <CheckCircle size={19} /> : <AlertIcon size={19} />}
      <span className="flex-1 text-[13.5px] font-medium">{message}</span>
      <button type="button" onClick={onDismiss} aria-label="إغلاق"><CloseIcon size={16} /></button>
    </div>
  );
}

/* --------------------------------------------------------------- others */

export function Segmented<T extends string>({ value, options, onChange }: {
  value: T;
  options: Array<{ value: T; label: string; badge?: number }>;
  onChange: (value: T) => void;
}) {
  return (
    <div role="tablist" className="flex gap-1 rounded-2xl bg-surface-2 p-1 border border-line/60">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => onChange(o.value)}
            className={`flex-1 rounded-xl py-2.5 text-[13.5px] font-semibold transition-colors
              ${active ? 'bg-surface-3 text-ink' : 'text-primary hover:text-primary-strong'}`}
          >
            {o.label}
            {o.badge ? <span className="sp-ltr">{'\u00a0'}({o.badge})</span> : null}
          </button>
        );
      })}
    </div>
  );
}

export function ProgressBar({ value, tone = 'primary', label }: {
  value: number; tone?: 'primary' | 'mint'; label?: string;
}) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? 'التقدّم'}
      className="h-2 w-full overflow-hidden rounded-pill bg-surface-3"
    >
      <div
        className={`sp-grow h-full rounded-pill ${tone === 'mint' ? 'bg-mint' : 'bg-primary'}`}
        style={{ width: `${pct}%`, transition: 'width 260ms ease' }}
      />
    </div>
  );
}

export function Retry({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick}
      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-primary">
      <RefreshIcon size={15} /> إعادة المحاولة
    </button>
  );
}
