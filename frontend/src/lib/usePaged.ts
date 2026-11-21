import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { apiPage, explain } from './api';

// How deep a list was read ("show more") is kept per history entry in sessionStorage (DEF-014).
// React Router's location.key lives in history.state, so it survives a reload and back/forward,
// while a fresh visit to the same address gets a new key and starts at the top. The URL stays
// clean, a shared link opens at the first page, and several lists on one page keep their own depth.
const PREFIX = 'telcron.paged:';
const CHUNK = 50; // the smallest maximum `limit` among the list endpoints
const MAX_DEPTH = 200; // a restore is at most four requests

function readDepth(key: string): number {
  try {
    const n = Number(sessionStorage.getItem(key));
    return Number.isFinite(n) && n > 0 ? Math.min(n, MAX_DEPTH) : 0;
  } catch {
    return 0;
  }
}

function writeDepth(key: string, n: number) {
  try {
    sessionStorage.setItem(key, String(n));
  } catch {
    // Storage full or disabled: the list still works, a reload just starts at the top.
  }
}

/** A paged list: on mount (and when deps change) as many items as this history entry had shown,
    at least one page; then `more()` appends the next page. */
export function usePaged<T>(path: string | null, pageSize = 12) {
  const { key: entry } = useLocation();
  const storeKey = `${PREFIX}${entry}:${path ?? ''}`;
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
      const want = Math.max(pageSize, readDepth(storeKey));
      const loaded: T[] = [];
      let more = true;
      while (more && loaded.length < want) {
        const page = await apiPage<T>(path, loaded.length, Math.min(want - loaded.length, CHUNK));
        if (mine !== generation.current) return;
        loaded.push(...page.items);
        more = page.hasMore && page.items.length > 0;
      }
      setItems(loaded);
      setHasMore(more);
    } catch (e) {
      if (mine === generation.current) setError(explain(e));
    } finally {
      if (mine === generation.current) setLoading(false);
    }
  }, [path, pageSize, storeKey]);

  const more = useCallback(async () => {
    if (!path) return;
    const mine = generation.current;
    setLoadingMore(true);
    try {
      const page = await apiPage<T>(path, items.length, pageSize);
      if (mine !== generation.current) return;
      setItems((prev) => [...prev, ...page.items]);
      setHasMore(page.hasMore);
      writeDepth(storeKey, items.length + page.items.length);
    } catch (e) {
      setError(explain(e));
    } finally {
      setLoadingMore(false);
    }
  }, [path, pageSize, items.length, storeKey]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { items, hasMore, loading, loadingMore, error, more, reload };
}
