import { BadgeCheck, CircleCheck, Star, ExternalLink, Globe, Landmark, Loader2, Megaphone, MessageSquareWarning, RefreshCw, ScrollText, TriangleAlert } from 'lucide-react';
import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { api, explain, MESSAGES, post, type Finding, type Research as ResearchT } from '../lib/api';
import { useAuth } from '../lib/auth';
import { track } from '../lib/researching';
import { Skeleton } from './ui';

const KIND: Record<Finding['kind'], { label: string; icon: typeof Globe; tone: string }> = {
  recall: { label: 'Recall', icon: Megaphone, tone: 'bg-danger-tint text-danger' },
  safety_warning: { label: 'Safety warning', icon: TriangleAlert, tone: 'bg-danger-tint text-danger' },
  complaint: { label: 'Complaint', icon: MessageSquareWarning, tone: 'bg-warn-tint text-warn' },
  review: { label: 'Review', icon: Star, tone: 'bg-gold-tint text-gold' },
  certification: { label: 'Certification', icon: BadgeCheck, tone: 'bg-ok-tint text-ok' },
  no_issue_found: { label: 'No issue found', icon: CircleCheck, tone: 'bg-ok-tint text-ok' },
  general: { label: 'Safety note', icon: ScrollText, tone: 'bg-neutral-tint text-muted' },
};
const SOURCE: Record<string, string> = {
  web_search: 'Web', regulator_web: 'Government regulator', uk_opss: 'UK Product Safety (OPSS)', openfda: 'US FDA',
  review_web: 'Review',
  community_web: 'Owner report',
};
const SITES: [RegExp, string][] = [
  [/(^|\.)reddit\.com$/, 'Reddit'], [/(^|\.)(x|twitter)\.com$/, 'X'], [/(^|\.)youtube\.com$/, 'YouTube'],
  [/(^|\.)quora\.com$/, 'Quora'], [/(^|\.)trustpilot\.com$/, 'Trustpilot'], [/(^|\.)amazon\./, 'Amazon reviews'],
  [/(^|\.)flipkart\.com$/, 'Flipkart reviews'], [/(^|\.)walmart\.com$/, 'Walmart reviews'],
  [/(^|\.)bestbuy\.com$/, 'Best Buy reviews'], [/(^|\.)ebay\./, 'eBay'], [/(^|\.)target\.com$/, 'Target reviews'],
];
/** "Reddit", "Amazon reviews"… for owner reports; the registry or "Web" otherwise. */
function sourceLabel(f: Finding) {
  const site = SITES.find(([re]) => re.test(host(f.url)));
  return site && (f.source === 'community_web' || f.source === 'web_search') ? site[1] : (SOURCE[f.source] ?? f.source);
}
const ORDER: Finding['kind'][] = ['recall', 'safety_warning', 'complaint', 'review', 'general', 'certification', 'no_issue_found'];

function host(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; }
}

/** What the recall registries and the web say about this product, each claim linked to its page. */
export function Research({ slug, name, onRated }: { slug: string; name: string; onRated: () => void }) {
  const { me } = useAuth();
  const [data, setData] = useState<ResearchT | null>(null);
  const [asking, setAsking] = useState(false);
  const [all, setAll] = useState(false);
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
      track(slug, name);
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
            US CPSC and FDA, UK Product Safety, government safety regulators (EU, Canada, Australia and others), the open web,
            and what owners report on Reddit, X, YouTube and marketplace reviews.
            Every line links to the page it comes from; a claim the page does not make is thrown away.
          </p>
        </div>
        {member && data.enabled && (
          <button className="btn-ghost btn-sm" onClick={ask} disabled={asking || busy || !data.can_request}
            title={data.can_request ? (data.unread ? 'Read the pages that were left' : 'Search again now') : data.unread ? 'Available a quarter of an hour after the last try' : MESSAGES[data.blocked ?? ''] ?? 'Searched in the last day'}>
            <RefreshCw className={`size-4 ${busy ? 'animate-spin' : ''}`} />{busy ? 'Searching…' : data.unread ? 'Read the rest' : 'Search again'}
          </button>
        )}
      </div>

      {busy && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-5 rounded-2xl bg-action-tint px-4 py-3 text-sm text-action">
          <p className="flex items-center gap-3"><Loader2 className="size-4 animate-spin" />{data.progress?.stage ?? 'Waiting its turn in the queue'}</p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/70">
            <motion.div className="h-full rounded-full bg-action" animate={{ width: `${data.progress?.percent ?? 3}%` }} transition={{ duration: 0.6 }} />
          </div>
          <p className="mt-2 text-xs text-action/80">This takes a minute or two. You can keep using Telcron: we tell you when it is done, and the passport updates itself.</p>
        </motion.div>
      )}

      {!busy && !data.unread && (data.blocked === 'research_daily_limit' || data.blocked === 'research_month_limit') && (
        <p className="mt-5 flex items-start gap-2 rounded-2xl bg-warn-tint px-4 py-3 text-sm text-warn">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          {!data.status
            ? data.blocked === 'research_daily_limit'
              ? 'Telcron has used today’s web-search allowance, so this product is waiting its turn. It is researched automatically as soon as the allowance frees up: no need to come back and press anything.'
              : 'Telcron has used this month’s web-search allowance. This product is researched automatically when it renews.'
            : MESSAGES[data.blocked]}
        </p>
      )}

      {!busy && data.unread > 0 && (
        <p className="mt-5 flex items-start gap-2 rounded-2xl bg-warn-tint px-4 py-3 text-sm text-warn">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          {data.unread} page{data.unread === 1 ? '' : 's'} could not be read yet: the free AI allowance was used up. Telcron reads them again automatically every 20 minutes{data.can_request ? ', or use “Read the rest” now.' : '.'}
        </p>
      )}

      {findings.length > 0 ? (
        <ul className="mt-5 space-y-3">
          {(all ? findings : findings.slice(0, 4)).map((f, i) => {
            const k = KIND[f.kind];
            return (
              <motion.li key={f.url + f.kind} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }} className="rounded-2xl border border-line p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`chip ${k.tone}`}><k.icon className="size-3.5" />{k.label}</span>
                  <span className="chip bg-panel text-muted">{sourceLabel(f)}</span>
                </div>
                <p className="mt-2 text-sm">{f.finding}</p>
                <a href={f.url} target="_blank" rel="noreferrer noopener" className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-action hover:underline">
                  {(() => { const t = f.title.replace(/\s+[|–-]\s+[^|–-]{2,40}$/, ''); return t.length > 90 ? t.slice(0, 90) + '…' : t; })()} <span className="font-normal text-muted">· {host(f.url)}</span><ExternalLink className="size-3" />
                </a>
              </motion.li>
            );
          })}
          {findings.length > 4 && (
            <li><button onClick={() => setAll(!all)} className="w-full rounded-2xl border border-dashed border-line py-2.5 text-sm font-semibold text-action transition hover:bg-panel">
              {all ? 'Show fewer' : `Show all ${findings.length} findings`}
            </button></li>
          )}
        </ul>
      ) : !busy && (
        <p className="mt-5 rounded-2xl bg-panel px-4 py-3 text-sm text-muted">
          {!data.status
            ? 'Not searched yet.'
 : data.unread > 0
              ? `Searched ${data.searched_at ? new Date(data.searched_at).toLocaleDateString() : ''}: ${data.stats?.pages ?? 0} pages found; nothing kept yet from the pages read so far.`
              : `Searched ${data.searched_at ? new Date(data.searched_at).toLocaleDateString() : ''}: ${data.stats?.pages ?? 0} pages read, none said anything about this product's safety or reliability.`}
        </p>
      )}
      {!busy && !data.unread && (data.stats?.errors?.filter((e) => !e.startsWith('reader')).length ?? 0) > 0 && (
        <p className="mt-3 text-xs text-muted">Some sources did not answer last time: {(data.stats?.errors ?? []).filter((e) => !e.startsWith('reader')).map((e) => e.split(':')[0]).join(', ')}.</p>
      )}
    </section>
  );
}
