/** Session context: configuration, token handling and the signed-in profile. */

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode,
} from 'react';
import { ApiError, api, readToken, writeToken } from './api';
import type { AppConfig, Profile } from './types';

interface SessionValue {
  config: AppConfig | null;
  profile: Profile | null;
  role: 'patient' | 'reviewer' | null;
  loading: boolean;
  error: ApiError | null;
  demoMode: boolean;
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
  retry: () => void;
  refreshProfile: () => void;
}

const Ctx = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [tick, setTick] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const cfg = await api.config();
      setConfig(cfg);
      if (readToken()) {
        try {
          const me = await api.me();
          setProfile(me.profile);
        } catch (err) {
          if (err instanceof ApiError && err.status === 401) {
            writeToken(null);
            setProfile(null);
          } else {
            throw err;
          }
        }
      } else {
        setProfile(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'unknown', 'تعذّر تحميل التطبيق.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load, tick]);

  const signIn = useCallback(async (token: string) => {
    writeToken(token);
    const me = await api.me();
    setProfile(me.profile);
  }, []);

  const signOut = useCallback(() => {
    writeToken(null);
    setProfile(null);
  }, []);

  const value = useMemo<SessionValue>(() => ({
    config,
    profile,
    role: profile?.role ?? null,
    loading,
    error,
    demoMode: config?.demo_mode ?? false,
    signIn,
    signOut,
    retry: () => setTick((n) => n + 1),
    refreshProfile: () => setTick((n) => n + 1),
  }), [config, profile, loading, error, signIn, signOut]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(Ctx);
  if (!value) throw new Error('useSession must be used inside <SessionProvider>');
  return value;
}
