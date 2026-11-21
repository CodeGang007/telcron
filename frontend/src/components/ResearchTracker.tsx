import { Loader2 } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { api, type Research } from '../lib/api';
import { onTrackedChange, tracked, untrack, type Tracked } from '../lib/researching';

type Live = Tracked & { percent: number; stage: string };

/** A small pill on every page while a product is being researched; a notice when it is done. */
export function ResearchTracker() {
  const [live, setLive] = useState<Live[]>([]);
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    const poll = async () => {
      const list = tracked();
      const next: Live[] = [];
      for (const t of list) {
        try {
          const r = await api<Research>(`/products/${t.slug}/research`);
          if (r.status === 'queued' || r.status === 'running') {
            next.push({ ...t, percent: r.progress?.percent ?? 5, stage: r.progress?.stage ?? 'Waiting its turn' });
          } else {
            untrack(t.slug);
            const n = r.findings.length;
            toast.success(`Research finished: ${t.name}`, {
              description: n ? `${n} sourced finding${n === 1 ? '' : 's'}; its passport is updated.` : 'Its passport is updated.',
              action: { label: 'View', onClick: () => navigate(`/products/${t.slug}`) },
            });
          }
        } catch {
          untrack(t.slug);
        }
      }
      if (alive) setLive(next);
      if (alive && next.length) timer = window.setTimeout(poll, 5000);
    };
    void poll();
    const off = onTrackedChange(() => { window.clearTimeout(timer); void poll(); });
    return () => { alive = false; window.clearTimeout(timer); off(); };
  }, [navigate]);

  const shown = live.filter((l) => pathname !== `/products/${l.slug}`);
  return (
    <AnimatePresence>
      {shown.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }}
          className="fixed bottom-24 left-4 z-30 w-72 space-y-2 lg:bottom-8 lg:left-8" aria-live="polite">
          {shown.map((l) => (
            <Link key={l.slug} to={`/products/${l.slug}`} className="block rounded-2xl border border-line bg-white/95 p-3 shadow-lift backdrop-blur transition hover:border-action">
              <p className="flex items-center gap-2 text-xs font-semibold"><Loader2 className="size-3.5 animate-spin text-action" />Researching {l.name}</p>
              <p className="mt-1 truncate text-[11px] text-muted">{l.stage}</p>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-neutral-tint">
                <motion.div className="h-full rounded-full bg-action" animate={{ width: `${l.percent}%` }} transition={{ duration: 0.6 }} />
              </div>
            </Link>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
