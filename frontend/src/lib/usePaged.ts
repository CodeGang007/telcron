import { useCallback, useEffect, useRef, useState } from 'react';
import { apiPage, explain } from './api';

/** A paged list: the first page on mount (and when deps change), then `more()` appends the next. */
export function usePaged<T>(path: string | null, pageSize = 12) {
  const [items, setItems] = useState<T[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);

  const reload = useCallback(async () => {
    const mine = ++generation.current;
    if (!path) {
      setItems([]);
      setHasMore(false);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const page = await apiPage<T>(path, 0, pageSize);
      if (mine !== generation.current) return;
      setItems(page.items);
      setHasMore(page.hasMore);
    } catch (e) {
      if (mine === generation.current) setError(explain(e));
    } finally {
      if (mine === generation.current) setLoading(false);
    }
  }, [path, pageSize]);

  const more = useCallback(async () => {
    if (!path) return;
    const mine = generation.current;
    setLoadingMore(true);
    try {
      const page = await apiPage<T>(path, items.length, pageSize);
      if (mine !== generation.current) return;
      setItems((prev) => [...prev, ...page.items]);
      setHasMore(page.hasMore);
    } catch (e) {
      setError(explain(e));
    } finally {
      setLoadingMore(false);
    }
  }, [path, pageSize, items.length]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { items, hasMore, loading, loadingMore, error, more, reload };
}
