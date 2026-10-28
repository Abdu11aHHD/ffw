/** Arabic-first formatting helpers.

Dates are written in words ("13 سبتمبر 2026") rather than ISO, because the
bidirectional algorithm reorders digit groups inside Arabic sentences. */

export const AR_MONTHS = [
  'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
  'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
];

export function arDate(value: string | Date | null | undefined): string {
  if (!value) return 'بلا تاريخ';
  const d = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return 'بلا تاريخ';
  return `${d.getDate()} ${AR_MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function arDateTime(value: string | Date | null | undefined): string {
  if (!value) return 'بلا تاريخ';
  const d = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return 'بلا تاريخ';
  const h = d.getHours();
  const m = d.getMinutes().toString().padStart(2, '0');
  const period = h < 12 ? 'صباحًا' : 'مساءً';
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${arDate(d)} — ${h12}:${m} ${period}`;
}

export function arPeriod(start: string | null, end: string | null): string {
  if (!start || !end) return 'فترة غير محددة';
  const a = new Date(start);
  const b = new Date(end);
  if (a.getFullYear() === b.getFullYear()) {
    return `${a.getDate()} ${AR_MONTHS[a.getMonth()]} إلى ${arDate(b)}`;
  }
  return `${arDate(a)} إلى ${arDate(b)}`;
}

export function arRelative(value: string): string {
  const d = new Date(value);
  const diff = Math.round((Date.now() - d.getTime()) / 86_400_000);
  if (diff <= 0) return 'اليوم';
  if (diff === 1) return 'أمس';
  if (diff < 7) return `قبل ${diff} أيام`;
  return arDate(d);
}

export function formatNumber(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'غير متاح';
  const factor = 10 ** decimals;
  const r = Math.round(value * factor) / factor;
  return Number.isInteger(r) ? String(r) : String(r);
}

export function formatMetric(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return 'غير متاح';
  return unit === '%' ? `${formatNumber(value)}%` : `${formatNumber(value)} ${unit}`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} بايت`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} كيلوبايت`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} ميغابايت`;
}

export function daysUntil(value: string): number {
  return Math.ceil((new Date(value).getTime() - Date.now()) / 86_400_000);
}
