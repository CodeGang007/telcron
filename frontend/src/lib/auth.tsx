import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { ApiError, api, explain, post, session, type Me, type Tokens } from './api';
import { onCoinsChanged } from './coins';

type Auth = {
  me: Me | null;
  loading: boolean;
  /** Set when there is a stored session but Telcron could not be reached (network or 5xx), so the
      member is not signed out, only not loaded yet (DEF-100). Null otherwise. */
  unreachable: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  reload: () => Promise<void>;
};
const Ctx = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [unreachable, setUnreachable] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!session.get()) {
      setMe(null);
      setUnreachable(null);
      setLoading(false);
      return;
    }
    try {
      setMe(await api<Me>('/auth/me'));
      setUnreachable(null);
    } catch (e) {
      // The server refusing the session signs the member out; a dropped connection or a 5xx does not.
      if (e instanceof ApiError && e.status < 500) {
        setMe(null);
        setUnreachable(null);
      } else {
        setUnreachable(explain(e));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    const onChange = () => {
      if (!session.get()) {
        setMe(null);
        setUnreachable(null);
      }
    };
    window.addEventListener('telcron:session', onChange);
    // The header's coin chip reads /coins whenever `me` changes; a fresh `me` after a spend or an
    // earn makes it read the new balance without Layout knowing about coin events (DEF-034).
    const offCoins = onCoinsChanged(() => void reload());
    // Coins confirmed while the tab was in the background show when the member comes back.
    const onVisible = () => { if (document.visibilityState === 'visible' && session.get()) void reload(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.removeEventListener('telcron:session', onChange);
      offCoins();
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [reload]);

  const signIn = async (email: string, password: string) => {
    session.set(await post<Tokens>('/auth/login', { email, password }));
    await reload();
  };
  const signOut = async () => {
    const current = session.get();
    if (current) await post('/auth/logout', { refresh_token: current.refresh_token }).catch(() => {});
    session.set(null);
  };
  return <Ctx.Provider value={{ me, loading, unreachable, signIn, signOut, reload }}>{children}</Ctx.Provider>;
}

export function useAuth(): Auth {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth outside AuthProvider');
  return ctx;
}
