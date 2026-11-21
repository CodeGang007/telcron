import { useCallback, useEffect, useState } from 'react';
import { explain, isNotFound } from './api';

/** Load on mount and when deps change; exposes loading, error text and a reload.
    `notFound` is set only when the server answered 404, so a page can tell "it does not exist"
    from "Telcron could not be reached" (DEF-036). */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps);
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      setData(await run());
    } catch (e) {
      setError(explain(e));
      setNotFound(isNotFound(e));
    } finally {
      setLoading(false);
    }
  }, [run]);
  useEffect(() => {
    void reload();
  }, [reload]);
  return { data, error, notFound, loading, reload };
}
