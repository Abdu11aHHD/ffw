/** Minimal data-fetching hook: loading, error, retry and manual refresh. */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from './api';

export interface AsyncState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
  setData: (value: T) => void;
}

export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const mounted = useRef(true);
  const ref = useRef(fetcher);
  ref.current = fetcher;

  useEffect(() => {
    mounted.current = true;
    const refresh = () => setTick(n => n + 1);
    window.addEventListener('focus', refresh);
    return () => { mounted.current = false; window.removeEventListener('focus', refresh); };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    ref.current()
      .then((value) => { if (!cancelled && mounted.current) setData(value); })
      .catch((err) => {
        if (cancelled || !mounted.current) return;
        setError(err instanceof ApiError ? err : new ApiError(0, 'unknown', 'حدث خطأ غير متوقع.'));
      })
      .finally(() => { if (!cancelled && mounted.current) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, error, loading, reload, setData };
}
