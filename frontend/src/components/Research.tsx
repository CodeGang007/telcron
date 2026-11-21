import { BadgeCheck, CircleCheck, ExternalLink, Globe, Landmark, Loader2, Megaphone, MessageSquareWarning, RefreshCw, ScrollText, TriangleAlert } from 'lucide-react';
import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { api, explain, post, type Finding, type Research as ResearchT } from '../lib/api';
import { useAuth } from '../lib/auth';
import { Skeleton } from './ui';

const KIND: Record<Finding['kind'], { label: string; icon: typeof Globe; tone: string }> = {
  recall: { label: 'Recall', icon: Megaphone, tone: 'bg-danger-tint text-danger' },
  safety_warning: { label: 'Safety warning', icon: TriangleAlert, tone: 'bg-danger-tint text-danger' },
  complaint: { label: 'Complaint', icon: MessageSquareWarning, tone: 'bg-warn-tint text-warn' },
  certification: { label: 'Certification', icon: BadgeCheck, tone: 'bg-ok-tint text-ok' },
  no_issue_found: { label: 'No issue found', icon: CircleCheck, tone: 'bg-ok-tint text-ok' },
  general: { label: 'Safety note', icon: ScrollText, tone: 'bg-neutral-tint text-muted' },
};
const SOURCE: Record<string, string> = {
  web_search: 'Web', regulator_web: 'Government regulator', uk_opss: 'UK Product Safety (OPSS)', openfda: 'US FDA',
};
const ORDER: Finding['kind'][] = ['recall', 'safety_warning', 'complaint', 'general', 'certification', 'no_issue_found'];

function host(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; }
}

/** What the recall registries and the web say about this product, each claim linked to its page. */
export function Research({ slug, onRated }: { slug: string; onRated: () => void }) {
  const { me } = useAuth();
  const [data, setData] = useState<ResearchT | null>(null);
  const [asking, setAsking] = useState(false);
  const busy = data?.status === 'queued' || data?.status === 'running';

  useEffect(() => {
    let alive = true;
    let wasBusy = false;
    const load = async () => {
      try {
        const r = await api<ResearchT>(`/products/${slug}/research`);
        if (!alive) return;
        setData(r);
        const nowBusy = r.status === 'queued' || r.status === 'running';
        if (wasBusy && !nowBusy) onRated(); // the passport was re-issued from what was found
        wasBusy = nowBusy;
        if (nowBusy) setTimeout(load, 4000);
      } catch {
        /* the passport still shows; research is extra */
      }
    };
    void load();
    return () => { alive = false; };
  }, [slug, onRated, asking]);

  const ask = async () => {
    setAsking(true);
    try {
      await post(`/products/${slug}/research`);
      toast.success('Searching recall registries and the web', { description: 'This takes about a minute.' });
    } catch (e) {
      toast.error(explain(e));
    } finally {
      setAsking(false);
    }
  };

  if (!data) return <div className="card"><Skeleton className="h-6 w-56" /><Skeleton className="mt-4 h-20 w-full" /></div>;
  const page = (u: string) => u.toLowerCase().replace(/^https?:\/\/(www\.)?/, '').replace(/\/[a-z]{2}(-[a-z]{2,4})?(?=\/)/, '').replace(/[?#].*$/, '').replace(/\/$/, '');
  const findings = data.findings
    .filter((f, i, all) => all.findIndex((o) => page(o.url) === page(f.url) || o.finding === f.finding) === i)
    .sort((a, b) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind));
  const member = !!me && me.verification_level >= 1;

  return (
    <section aria-labelledby="research" className="card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="research" className="flex items-center gap-2 font-display text-xl font-bold"><Landmark className="size-5 text-brand-ink" />What official sources and the web say</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            US CPSC and FDA, UK Product Safety, government safety regulators (EU, Canada, Australia and others) and the open web.
            Every line links to the page it comes from; a claim the page does not make is thrown away.
          </p>
        </div>
        {member && data.enabled && (
          <button className="btn-ghost btn-sm" onClick={ask} disabled={asking || busy || !data.can_request} title={data.can_request ? 'Search again now' : 'Searched in the last day'}>
            <RefreshCw className={`size-4 ${busy ? 'animate-spin' : ''}`} />{busy ? 'Searching…' : 'Search again'}
          </button>
        )}
      </div>

      {busy && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-5 flex items-center gap-3 rounded-2xl bg-action-tint px-4 py-3 text-sm text-action">
          <Loader2 className="size-4 animate-spin" />Searching recall registries and the web, then reading what they say. The passport updates when it is done.
        </motion.div>
      )}

      {findings.length > 0 ? (
        <ul className="mt-5 space-y-3">
          {findings.map((f, i) => {
            const k = KIND[f.kind];
            return (
              <motion.li key={f.url + f.kind} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }} className="rounded-2xl border border-line p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`chip ${k.tone}`}><k.icon className="size-3.5" />{k.label}</span>
                  <span className="chip bg-panel text-muted">{SOURCE[f.source] ?? f.source}</span>
                </div>
                <p className="mt-2 text-sm">{f.finding}</p>
                <a href={f.url} target="_blank" rel="noreferrer noopener" className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-action hover:underline">
                  {f.title.length > 90 ? f.title.slice(0, 90) + '…' : f.title} <span className="font-normal text-muted">· {host(f.url)}</span><ExternalLink className="size-3" />
                </a>
              </motion.li>
            );
          })}
        </ul>
      ) : !busy && (
        <p className="mt-5 rounded-2xl bg-panel px-4 py-3 text-sm text-muted">
          {data.status
            ? `Searched ${data.searched_at ? new Date(data.searched_at).toLocaleDateString() : ''}: ${data.stats?.pages ?? 0} pages read, none said anything about this product's safety.`
            : 'Not searched yet.'}
        </p>
      )}
      {data.stats && data.stats.errors.length > 0 && !busy && (
        <p className="mt-3 text-xs text-muted">Some sources did not answer last time: {data.stats.errors.map((e) => e.split(':')[0]).join(', ')}.</p>
      )}
    </section>
  );
}
