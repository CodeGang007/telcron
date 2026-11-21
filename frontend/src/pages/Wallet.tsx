import { AlertTriangle, BellRing, Hourglass, PackagePlus, ScanLine, ShieldCheck, Trash2, Wallet as WalletIcon } from 'lucide-react';
import { AnimatePresence, LayoutGroup, motion } from 'motion/react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Gate } from '../components/Gate';
import { AnimatedNumber, CardSkeletons, EmptyState, Notice, PageTitle, Pager, StatusBadge, scoreTone } from '../components/ui';
import { api, explain, post } from '../lib/api';
import { useLoad } from '../lib/useLoad';
import { usePaged } from '../lib/usePaged';

type WalletItem = {
  id: string; product_id: string; slug: string; name: string; brand: string | null; nickname: string | null;
  status: string; status_badge: string | null; trust_score: number | null; passport_changed: boolean; created_at: string;
};
type Alert = { id: string; severity: string; event_type: string; title: string; summary: string | null; product_slug: string; created_at: string };

const SEVERITY: Record<string, string> = {
  critical: 'bg-danger text-white', high: 'bg-danger-tint text-danger', medium: 'bg-warn-tint text-warn', low: 'bg-neutral-tint text-muted', info: 'bg-neutral-tint text-muted',
};
const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'attention', label: 'Needs attention' },
  { key: 'verified', label: 'Verified' },
] as const;
const needsAttention = (i: WalletItem) => i.passport_changed || ['recalled', 'certification_issue'].includes(i.status_badge ?? '');

function ItemCard({ item, onRemove }: { item: WalletItem; onRemove: (i: WalletItem) => void }) {
  const alarming = ['recalled', 'certification_issue'].includes(item.status_badge ?? '');
  return (
    <motion.li
      layout
      initial={{ opacity: 0, scale: 0.94, y: 16 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9, x: -40, transition: { duration: 0.25 } }}
      transition={{ type: 'spring', stiffness: 260, damping: 26 }}
      className={`group relative overflow-hidden rounded-3xl border bg-white p-5 shadow-soft transition hover:shadow-lift ${alarming ? 'border-danger/40' : 'border-line'}`}
    >
      {alarming && <span className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-danger to-warn" />}
      <div className="flex items-start justify-between gap-3">
        <StatusBadge badge={item.status_badge} />
        {/* Always visible and finger-sized: a phone has no hover to reveal it (DEF-038). */}
        <button
          onClick={() => onRemove(item)}
          className="-mr-2 -mt-2 grid size-11 shrink-0 place-items-center rounded-full text-muted transition hover:bg-danger-tint hover:text-danger focus-visible:bg-danger-tint focus-visible:text-danger"
          aria-label={`Remove ${item.name} from your wallet`}
          title="Remove from wallet"
        >
          <Trash2 className="size-5" />
        </button>
      </div>
      <Link to={`/products/${item.slug}`} className="mt-4 block font-display text-lg font-bold leading-snug hover:text-brand-ink">{item.nickname ?? item.name}</Link>
      <p className="text-sm text-muted">{item.nickname ? item.name : item.brand}</p>
      <div className="mt-5 flex items-end justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">Trust</p>
          <p className="font-display text-2xl font-extrabold" style={{ color: scoreTone(item.trust_score) }}>{item.trust_score === null ? '—' : Math.round(item.trust_score)}</p>
        </div>
        {item.passport_changed && (
          <span className="chip bg-warn-tint text-warn">
            <span className="relative flex size-2"><span className="absolute inline-flex size-full animate-ping rounded-full bg-warn opacity-75" /><span className="relative inline-flex size-2 rounded-full bg-warn" /></span>
            Passport changed since you saved it
          </span>
        )}
        {item.status === 'pending_verification' && <span className="chip bg-neutral-tint text-muted"><Hourglass className="size-3.5" />Awaiting ownership check; no alerts yet</span>}
      </div>
    </motion.li>
  );
}

function WalletBody() {
  const items = useLoad(() => api<WalletItem[]>('/wallet/items'), []);
  const alerts = usePaged<Alert>('/alerts', 6);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]['key']>('all');
  const [removed, setRemoved] = useState<Set<string>>(new Set());

  const list = useMemo(() => (items.data ?? []).filter((i) => !removed.has(i.id)), [items.data, removed]);
  const shown = list.filter((i) => (filter === 'all' ? true : filter === 'attention' ? needsAttention(i) : i.status_badge === 'verified'));
  const remove = async (item: WalletItem) => {
    setRemoved((s) => new Set(s).add(item.id));
    try {
      await api(`/wallet/items/${item.id}`, { method: 'DELETE' });
      toast.success('Removed from your wallet', { description: item.name, duration: 8000, action: { label: 'Undo', onClick: () => void undo(item) } });
    } catch (e) {
      setRemoved((s) => { const n = new Set(s); n.delete(item.id); return n; });
      toast.error(explain(e));
    }
  };
  // Undo saves the product again (a new wallet item, same product), then reads the wallet back.
  const undo = async (item: WalletItem) => {
    try {
      await post('/wallet/items', { product_id: item.product_id, ...(item.nickname ? { nickname: item.nickname } : {}) });
      toast.success('Back in your wallet', { description: item.name });
      await items.reload();
    } catch (e) {
      toast.error(explain(e));
    }
  };

  if (items.loading) return <CardSkeletons count={3} />;
  if (items.error)
    return <Notice tone="error">{items.error} <button className="font-semibold underline" onClick={() => void items.reload()}>Try again</button></Notice>;
  return (
    <>
      <motion.dl initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.08 } } }} className="mb-10 grid gap-4 sm:grid-cols-3">
        {[
          { label: 'Products you own', value: list.length, icon: WalletIcon, cls: 'from-brand-bright to-brand-deep' },
          { label: 'Verified safe', value: list.filter((i) => i.status_badge === 'verified').length, icon: ShieldCheck, cls: 'from-ok-bright to-ok-deep' },
          { label: 'Need your attention', value: list.filter(needsAttention).length, icon: AlertTriangle, cls: 'from-gold to-warn-bright' },
        ].map((s) => (
          <motion.div key={s.label} variants={{ hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }} className={`relative overflow-hidden rounded-3xl bg-gradient-to-br p-6 text-white shadow-lift ${s.cls}`}>
            <s.icon className="absolute -bottom-4 -right-4 size-24 opacity-15" />
            <dt className="text-sm text-white/80">{s.label}</dt>
            <dd className="mt-1 font-display text-4xl font-extrabold"><AnimatedNumber value={s.value} /></dd>
          </motion.div>
        ))}
      </motion.dl>

      <div className="grid gap-10 lg:grid-cols-[1fr_22rem]">
        <section aria-label="Saved products">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <LayoutGroup>
              <div className="flex gap-1 rounded-full bg-panel p-1">
                {FILTERS.map((f) => (
                  <button key={f.key} onClick={() => setFilter(f.key)} className={`relative rounded-full px-4 py-1.5 text-xs font-semibold transition ${filter === f.key ? 'text-ink' : 'text-muted'}`}>
                    {filter === f.key && <motion.span layoutId="wallet-filter" className="absolute inset-0 rounded-full bg-white shadow-soft" />}
                    <span className="relative">{f.label}</span>
                  </button>
                ))}
              </div>
            </LayoutGroup>
            <Link to="/scan" className="btn btn-sm"><ScanLine className="size-4" />Add by scanning</Link>
          </div>
          {list.length === 0 ? (
            <EmptyState icon={PackagePlus} title="Your wallet is empty" action={<Link className="btn" to="/search">Find a product you own</Link>}>
              Save the products you own and Telcron watches them for you: recalls, certificates and hazard scores.
            </EmptyState>
          ) : shown.length === 0 ? (
            <EmptyState icon={ShieldCheck} title="Nothing here">No product matches this filter.</EmptyState>
          ) : (
            <motion.ul layout className="grid gap-4 sm:grid-cols-2">
              <AnimatePresence mode="popLayout">
                {shown.map((i) => <ItemCard key={i.id} item={i} onRemove={remove} />)}
              </AnimatePresence>
            </motion.ul>
          )}
        </section>

        <aside aria-labelledby="alerts-title">
          <h2 id="alerts-title" className="flex items-center gap-2 font-display text-xl font-bold"><BellRing className="size-5 text-brand-ink" />Risk alerts</h2>
          {alerts.error && <div className="mt-4"><Notice tone="error">{alerts.error}</Notice></div>}
          {alerts.items.length === 0 && !alerts.loading && !alerts.error ? (
            <div className="mt-4 rounded-3xl border border-dashed border-line p-6 text-center text-sm text-muted">
              <ShieldCheck className="mx-auto mb-2 size-8 text-ok" />No alerts. We watch your saved products for you.
            </div>
          ) : (
            <ol className="mt-4 space-y-3">
              {alerts.items.map((a, i) => (
                <motion.li key={a.id} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} className="rounded-2xl border border-line bg-white p-4 shadow-soft">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`chip !py-0.5 uppercase ${SEVERITY[a.severity] ?? SEVERITY.info}`}>{a.severity}</span>
                    <span className="text-xs text-muted">{new Date(a.created_at).toLocaleDateString()}</span>
                  </div>
                  <Link to={`/products/${a.product_slug}`} className="mt-2 block text-sm font-semibold hover:text-brand-ink">{a.title}</Link>
                </motion.li>
              ))}
            </ol>
          )}
          <Pager hasMore={alerts.hasMore} loading={alerts.loadingMore} onMore={alerts.more} shown={alerts.items.length} />
        </aside>
      </div>
    </>
  );
}

export function Wallet() {
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Digital Wallet" title="Products you own" icon={WalletIcon}>
        Save what you own and Telcron alerts you when a recall, a certificate or a hazard score changes.
      </PageTitle>
      <Gate><WalletBody /></Gate>
    </div>
  );
}
