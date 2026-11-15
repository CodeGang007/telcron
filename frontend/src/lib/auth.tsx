import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, post, session, type Me, type Tokens } from './api';

type Auth = {
  me: Me | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  reload: () => Promise<void>;
};
const Ctx = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!session.get()) {
      setMe(null);
      setLoading(false);
      return;
    }
    try {
      setMe(await api<Me>('/auth/me'));
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    const onChange = () => {
      if (!session.get()) setMe(null);
    };
    window.addEventListener('telcron:session', onChange);
    return () => window.removeEventListener('telcron:session', onChange);
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
  return <Ctx.Provider value={{ me, loading, signIn, signOut, reload }}>{children}</Ctx.Provider>;
}

export function useAuth(): Auth {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth outside AuthProvider');
  return ctx;
}
