/** PDF upload with real progress, cancellation, retry and honest status.
 *  The screen never claims processing finished before the backend says so. */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Notice, ProgressBar } from '../components/ui';
import { CloseIcon, Icon } from '../components/Icons';
import { ApiError, api, uploadReport } from '../lib/api';
import { formatFileSize } from '../lib/format';
import { SukkarHeader, SukkarScreen } from './SukkarChrome';

type Phase = 'idle' | 'uploading' | 'processing' | 'done' | 'failed';

const MAX_BYTES = 15 * 1024 * 1024;
const POLL_MS = 1200;
const POLL_LIMIT = 180;

export default function SukkarUpload() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const timerRef = useRef<number | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [statusLabel, setStatusLabel] = useState('');
  const [reportId, setReportId] = useState<string | null>(null);

  useEffect(() => () => {
    cancelRef.current?.();
    if (timerRef.current) window.clearTimeout(timerRef.current);
  }, []);

  const pick = (selected: File | null) => {
    setError(null);
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith('.pdf')) {
      setError('نوع الملف غير مدعوم. يُقبل ملف PDF فقط.');
      setFile(null);
      return;
    }
    if (selected.size === 0) {
      setError('الملف فارغ.');
      setFile(null);
      return;
    }
    if (selected.size > MAX_BYTES) {
      setError(`حجم الملف ${formatFileSize(selected.size)} وهو أكبر من الحد المسموح (15 ميغابايت).`);
      setFile(null);
      return;
    }
    setFile(selected);
    setPhase('idle');
    setProgress(0);
  };

  const poll = useCallback((id: string, attempt = 0) => {
    api.reportStatus(id)
      .then((s) => {
        setStatusLabel(s.status_label_ar);
        if (s.failed) {
          setPhase('failed');
          setError(s.error_ar ?? 'تعذّرت معالجة التقرير.');
          return;
        }
        if (s.ready) {
          setPhase('done');
          return;
        }
        if (attempt >= POLL_LIMIT) {
          setPhase('failed');
          setError('استغرقت المعالجة وقتًا أطول من المتوقع. حدّث الصفحة أو حاول مرة أخرى.');
          return;
        }
        timerRef.current = window.setTimeout(() => poll(id, attempt + 1), POLL_MS);
      })
      .catch((err) => {
        setPhase('failed');
        setError(err instanceof ApiError ? err.messageAr : 'تعذّر الاتصال بالخادم.');
      });
  }, []);

  async function start() {
    if (!file) return;
    setPhase('uploading');
    setProgress(0);
    setError(null);
    const { promise, cancel } = uploadReport(file, setProgress);
    cancelRef.current = cancel;
    try {
      const res = await promise;
      cancelRef.current = null;
      setReportId(res.report.id);
      setPhase('processing');
      setStatusLabel(res.report.status_label_ar);
      poll(res.report.id);
    } catch (err) {
      cancelRef.current = null;
      if (err instanceof ApiError && err.code === 'cancelled') {
        setPhase('idle');
        setProgress(0);
        return;
      }
      setPhase('failed');
      setError(err instanceof ApiError ? err.messageAr : 'تعذّر رفع الملف.');
    }
  }

  function reset() {
    cancelRef.current?.();
    if (timerRef.current) window.clearTimeout(timerRef.current);
    setFile(null);
    setPhase('idle');
    setProgress(0);
    setError(null);
    setReportId(null);
    if (inputRef.current) inputRef.current.value = '';
  }

  return (
    <SukkarScreen header={<SukkarHeader title="رفع تقرير السكر" subtitle="تقريرك جاهز؟ خلّنا نشوف وش يقول" />}>
      <div className="sp-enter space-y-5">
        <Notice tone="mint" icon="glucose" title="خطوة بسيطة لاستعداد أفضل لموعدك">
          اختر ملف PDF نصي مُصدَّر من تطبيق الحساس أو المضخة. لا نقرأ بيانات الإنسولين
          ولا إعدادات المضخة. قد يتضمن الملف هوية شخصية؛ استخدم ملف التجربة في وضع العرض.
        </Notice>
        <a className="block rounded-xl border border-line px-4 py-3 text-[13px] text-primary" href="/demo/synthetic-discover.pdf" download>
          تنزيل تقرير اصطناعي للتجربة — لا يخص مريضًا حقيقيًا
        </a>

        {/* ---------------------------------------------- file picker */}
        <Card className="p-4">
          <input
            ref={inputRef}
            id="report-file"
            type="file"
            accept="application/pdf,.pdf"
            className="sr-only"
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
            disabled={phase === 'uploading' || phase === 'processing'}
          />

          {!file ? (
            <label
              htmlFor="report-file"
              className="sp-pressable flex cursor-pointer flex-col items-center gap-2.5
                rounded-tile border border-dashed border-line py-8 text-center"
            >
              <span className="grid place-items-center size-12 rounded-2xl bg-primary-soft text-primary">
                <Icon name="upload" size={24} />
              </span>
              <span className="text-[14px] font-semibold text-ink">اختر ملف PDF</span>
              <span className="text-[12px] text-ink-3">PDF فقط — حتى 15 ميغابايت</span>
            </label>
          ) : (
            <div>
              <div className="flex items-center gap-3">
                <span className="grid place-items-center size-10 shrink-0 rounded-xl
                  bg-primary-soft text-primary">
                  <Icon name="document" size={19} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-semibold text-ink">{file.name}</p>
                  <p className="text-[12px] text-ink-3">{formatFileSize(file.size)}</p>
                </div>
                {phase === 'idle' && (
                  <button type="button" onClick={reset} aria-label="إزالة الملف"
                    className="sp-pressable grid size-8 place-items-center rounded-lg text-ink-3">
                    <CloseIcon size={16} />
                  </button>
                )}
              </div>

              {(phase === 'uploading' || phase === 'processing') && (
                <div className="mt-4 space-y-2">
                  <ProgressBar
                    value={phase === 'uploading' ? progress : 100}
                    tone={phase === 'processing' ? 'mint' : 'primary'}
                    label="تقدّم الرفع"
                  />
                  <p className="text-[12.5px] text-ink-2">
                    {phase === 'uploading'
                      ? <>جارٍ الرفع… <span className="sp-ltr">{progress}%</span></>
                      : statusLabel || 'جارٍ تجهيز التقرير…'}
                  </p>
                </div>
              )}
            </div>
          )}
        </Card>

        {error && (
          <Notice tone="danger" title="تعذّر إتمام العملية">{error}</Notice>
        )}

        {/* --------------------------------------------------- actions */}
        {phase === 'idle' && (
          <Button full icon="upload" disabled={!file} onClick={() => void start()}>
            رفع التقرير
          </Button>
        )}

        {phase === 'uploading' && (
          <Button full variant="secondary" onClick={() => cancelRef.current?.()}>
            إلغاء الرفع
          </Button>
        )}

        {phase === 'processing' && (
          <Button full variant="secondary" loading>جارٍ المعالجة…</Button>
        )}

        {phase === 'failed' && (
          <div className="flex gap-2.5">
            <Button className="flex-1" onClick={() => void start()} disabled={!file}>
              إعادة المحاولة
            </Button>
            <Button variant="secondary" className="flex-1" onClick={reset}>اختيار ملف آخر</Button>
          </div>
        )}

        {phase === 'done' && reportId && (
          <div className="sp-enter space-y-3">
            <Notice tone="ok" icon="check" title="تم بنجاح">
              انتهت المعالجة. يمكنك الآن مراجعة المؤشرات المستخرجة ومصدر كل قيمة.
            </Notice>
            <Button full variant="mint" onClick={() => navigate(`/my-profile/diabetes-journey/reports/${reportId}`)}>
              افتح التقرير
            </Button>
            <Button full variant="ghost" onClick={reset}>رفع تقرير آخر</Button>
          </div>
        )}

        <Card className="p-4">
          <p className="mb-2 text-[13.5px] font-semibold text-ink">ما الذي نقبله؟</p>
          <ul className="space-y-1.5 text-[12.5px] leading-relaxed text-ink-2">
            <li>• ملف PDF يحتوي نصًا (وليس صورة ممسوحة ضوئيًا).</li>
            <li>• صفحة ملخص المؤشرات من تقرير الحساس أو المضخة.</li>
            <li>• فترة 14 يومًا على الأقل لتكون المؤشرات قابلة للتقييم.</li>
            <li>• ملفات غير مشفّرة ولا محمية بكلمة مرور.</li>
          </ul>
        </Card>
      </div>
    </SukkarScreen>
  );
}
