import {
  AlertOctagon,
  BadgeCheck,
  Bot,
  ChevronDown,
  FileText,
  Flag,
  Heart,
  History,
  MessageSquarePlus,
  PencilLine,
  ShieldCheck,
  Star,
  ThumbsUp,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useCallback, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { FactForm, FlagForm } from '../components/Contribute';
import { Alternatives, StoreLinks } from '../components/Alternatives';
import { Assistant } from '../components/Assistant';
import { Research } from '../components/Research';
import { CategoryTile, EmptyState, Notice, Pager, Skeleton, Stars, StatusBadge, TrustRing, scoreTone } from '../components/ui';
import { api, apiUrl, explain, post, type Dimension, type Passport, type ProductDetail, type Review } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useLoad } from '../lib/useLoad';
import { usePaged } from '../lib/usePaged';

const VERDICT: Record<string, string> = { match: 'Matches this product', near_match: 'May match this product' };
const CERT: Record<string, string> = { valid: 'bg-ok-tint text-ok', expired: 'bg-danger-tint text-danger', revoked: 'bg-danger-tint text-danger', not_checked: 'bg-neutral-tint text-muted' };

/** "Samsung Recalls X | CPSC.gov" -> "Samsung Recalls X": the site name is shown with the link. */
export const cleanTitle = (t: string) => t.replace(/\s+[|–-]\s+[^|–-]{2,40}$/, '').trim();

/** One sentence on what the passport means for someone holding this product. */
function Verdict({ pass, recalls }: { pass: Passport; recalls: Passport['recall_matches'] }) {
  const high = (pass.hazard?.total_score ?? 0) >= 60;
  const sentence = (t: string | null | undefined, fallback: string) => (t ? (/[.!?]$/.test(t.trim()) ? t.trim() : `${t.trim()}.`) : fallback);
  const match = recalls.find((r) => r.verdict === 'match');
  const near = recalls.find((r) => r.verdict === 'near_match');
  const [tone, title, text] = match
    ? ['danger', 'This product is recalled', `${sentence(match.hazard, 'An official recall notice names this product.')} Stop using it and follow the notice's remedy.`]
    : near
      ? ['danger', 'Official recall notices may cover this product', `${sentence(near.hazard, 'A recall names this brand and a product like it.')} Check the notices below against your model and serial number.`]
      : pass.status_badge === 'certification_issue'
        ? ['warn', 'A certificate problem was found', 'One of its certificates has expired or been revoked. See the details below.']
        : high
          ? ['warn', 'Serious hazards are reported', 'Sources describe a high hazard on at least one dimension. Open the hazard scores to see the evidence.']
          : pass.status_badge === 'verified'
            ? ['ok', 'No recall found, checks passed', 'No recall notice matches it, and nothing we found shows a serious hazard. We keep checking.']
            : ['neutral', 'Not enough is known yet', 'We have not found enough evidence to rate it. Research runs when a product is added; reviews and reports help too.'];
  const style = { danger: 'border-danger/30 bg-danger-tint text-danger', warn: 'border-warn/30 bg-warn-tint text-warn', ok: 'border-ok/30 bg-ok-tint text-ok', neutral: 'border-line bg-panel text-muted' }[tone as 'danger'];
  const Icon = tone === 'ok' ? BadgeCheck : AlertOctagon;
  return (
    <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} role={tone === 'danger' ? 'alert' : undefined}
      className={`flex items-start gap-3 border-b px-6 py-4 sm:px-8 ${style}`}>
      <Icon className="mt-0.5 size-5 shrink-0" />
      <div><p className="font-semibold">{title}</p><p className="mt-0.5 text-sm text-ink/80">{text}</p></div>
    </motion.div>
  );
}

function hazardTone(score: number) {
  return score >= 60 ? 'var(--color-danger)' : score >= 30 ? 'var(--color-gold)' : 'var(--color-ok)';
}

function DimensionRow({ d, index }: { d: Dimension; index: number }) {
  const [open, setOpen] = useState(false);
  const scored = d.status === 'scored' && d.score !== null;
  return (
    <li className="py-4">
      <button className="w-full text-left" onClick={() => setOpen(!open)} aria-expanded={open} disabled={!d.citations.length}>
        <div className="flex items-baseline justify-between gap-4">
          <p className="font-medium">{d.name}</p>
          <p className="flex items-center gap-2 text-sm text-muted">
            {scored ? <span className="font-semibold" style={{ color: hazardTone(d.score!) }}>{Math.round(d.score!)}</span> : 'No evidence'}
            {d.citations.length > 0 && <ChevronDown className={`size-4 transition ${open ? 'rotate-180' : ''}`} />}
          </p>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-neutral-tint" aria-hidden>
          <motion.div
            className="h-full rounded-full"
            style={{ background: scored ? hazardTone(d.score!) : 'transparent' }}
            initial={{ width: 0 }}
            whileInView={{ width: `${scored ? Math.max(3, d.score!) : 0}%` }}
            viewport={{ once: true }}
            transition={{ duration: 0.9, delay: index * 0.06, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>
        {d.justification && <p className="mt-2 text-sm text-muted">{d.justification}</p>}
      </button>
      <AnimatePresence>
        {open && (
          <motion.ul initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="mt-3 space-y-2 overflow-hidden">
            {d.citations.map((c) => (
              <li key={c.id} className="rounded-xl border border-line bg-panel/60 px-3 py-2 text-sm text-muted">
                <span className="mr-2 text-[10px] font-bold uppercase tracking-wider text-ink">{c.kind === 'web_document' ? 'source' : c.kind.replace('_', ' ')}</span>
                {c.excerpt}
                {c.url && <a href={c.url} target="_blank" rel="noreferrer noopener" className="ml-2 text-xs font-semibold text-action hover:underline">open</a>}
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </li>
  );
}

function ReviewForm({ slug, onDone }: { slug: string; onDone: () => void }) {
  const [rating, setRating] = useState(5);
  const [hover, setHover] = useState(0);
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await post<{ coins_pending: number }>(`/products/${slug}/reviews`, { rating, body });
      toast.success('Review posted', { description: `${r.coins_pending} TelCoins are pending while we check it.` });
      setBody('');
      onDone();
    } catch (err) {
      toast.error(explain(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="space-y-4" aria-label="Write a review">
      <div>
        <p className="text-sm font-medium">Your rating</p>
        <div className="mt-1 flex gap-1" onMouseLeave={() => setHover(0)}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button type="button" key={n} aria-label={`${n} out of 5`} onMouseEnter={() => setHover(n)} onClick={() => setRating(n)} className="transition hover:scale-110">
              <Star className={`size-7 ${(hover || rating) >= n ? 'fill-gold text-gold' : 'text-line'}`} />
            </button>
          ))}
        </div>
      </div>
      <label className="block text-sm font-medium">
        Your experience (at least 20 characters)
        <textarea className="field mt-1 min-h-28 font-normal" required minLength={20} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} placeholder="What happened when you used it?" />
      </label>
      <button className="btn w-full" disabled={busy}>{busy ? 'Posting…' : 'Post review'}</button>
    </form>
  );
}

const TABS = [
  { key: 'review', label: 'Review', icon: MessageSquarePlus },
  { key: 'flag', label: 'Report hazard', icon: Flag },
  { key: 'fact', label: 'Correction', icon: PencilLine },
] as const;

function Contribute({ slug, onReview }: { slug: string; onReview: () => void }) {
  const [tab, setTab] = useState<(typeof TABS)[number]['key']>('review');
  return (
    <div className="card">
      <div className="mb-5 flex gap-1 rounded-2xl bg-panel p-1">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`relative flex flex-1 items-center justify-center gap-1.5 rounded-xl px-2 py-2 text-xs font-semibold transition ${tab === t.key ? 'text-ink' : 'text-muted'}`}>
            {tab === t.key && <motion.span layoutId="contribute-tab" className="absolute inset-0 rounded-xl bg-white shadow-soft" />}
            <t.icon className="relative size-3.5" /><span className="relative">{t.label}</span>
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.18 }}>
          {tab === 'review' && <ReviewForm slug={slug} onDone={onReview} />}
          {tab === 'flag' && <FlagForm slug={slug} />}
          {tab === 'fact' && <FactForm slug={slug} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function ProductSkeleton() {
  return (
    <div className="container-page space-y-8 py-12">
      <div className="flex items-center gap-5"><Skeleton className="size-24 rounded-3xl" /><div className="flex-1 space-y-3"><Skeleton className="h-4 w-32" /><Skeleton className="h-8 w-2/3" /></div></div>
      <Skeleton className="h-72 w-full rounded-[2rem]" />
      <Skeleton className="h-48 w-full rounded-3xl" />
    </div>
  );
}

export function Product() {
  const { slug = '' } = useParams();
  const { me } = useAuth();
  const product = useLoad(() => api<ProductDetail>(`/products/${slug}`), [slug]);
  const passport = useLoad(() => api<Passport>(`/products/${slug}/passport`).catch(() => null), [slug]);
  const reviews = usePaged<Review>(`/products/${slug}/reviews`, 5);
  const [saved, setSaved] = useState(false);
  const rated = useCallback(() => { void passport.reload(); void product.reload(); }, [passport.reload, product.reload]);

  if (product.loading) return <ProductSkeleton />;
  if (product.error || !product.data)
    return (
      <div className="container-page py-16">
        <EmptyState icon={AlertOctagon} title="We could not find that product" action={<Link className="btn" to="/search">Search again</Link>} />
      </div>
    );
  const p = product.data;
  const pass = passport.data;
  const canContribute = !!me && me.verification_level >= 1;
  // One card per notice, however many addresses or copies it was found under.
  const noticeKey = (t: string) => t.toLowerCase().replace(/\s*\|.*$/, '').replace(/[^a-z0-9]+/g, ' ').trim();
  const recalls = pass
    ? pass.recall_matches.filter((r, i, all) => r.verdict !== 'rejected' && all.findIndex((o) => noticeKey(o.title) === noticeKey(r.title)) === i)
    : [];
  const stub = pass?.hazard?.model_code.startsWith('stub');

  const save = async () => {
    try {
      await post('/wallet/items', { product_id: p.slug });
      setSaved(true);
      toast.success('Saved to your Digital Wallet', { description: 'We will alert you if its passport changes.' });
    } catch (e) {
      toast.error(explain(e));
    }
  };

  return (
    <div className="container-page py-10">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-wrap items-start justify-between gap-6">
        <div className="flex items-start gap-5">
          {p.image_url ? (
            <img src={apiUrl(p.image_url)} alt={p.name} className="size-24 rounded-3xl border border-line bg-white object-cover shadow-soft" />
          ) : (
            <CategoryTile category={p.category} size="lg" />
          )}
          <div>
            <p className="eyebrow">{p.category}</p>
            <h1 className="mt-1 max-w-2xl font-display text-3xl font-extrabold tracking-tight sm:text-4xl">{p.name}</h1>
            <p className="mt-2 text-muted">{[p.brand, p.model_number].filter(Boolean).join(' · ')}</p>
            <details className="group mt-3">
              <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-xs font-medium text-muted hover:text-ink">Where to buy<span className="transition group-open:rotate-180">▾</span></summary>
              <div className="mt-2"><StoreLinks product={p} /></div>
            </details>
          </div>
        </div>
        <div className="flex gap-2">
          {canContribute ? (
            <motion.button whileTap={{ scale: 0.94 }} className={saved ? 'btn-ghost' : 'btn'} onClick={save} disabled={saved}>
              <Heart className={`size-4 ${saved ? 'fill-brand-ink text-brand-ink' : ''}`} />{saved ? 'In your wallet' : 'Save to wallet'}
            </motion.button>
          ) : (
            <Link className="btn-ghost" to="/sign-in"><Heart className="size-4" />Sign in to save</Link>
          )}
        </div>
      </motion.div>

      <section aria-labelledby="passport" className="mt-10 overflow-hidden rounded-[2rem] border border-line bg-gradient-to-br from-white to-panel shadow-lift">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line px-6 py-4 sm:px-8">
          <h2 id="passport" className="flex items-center gap-2 font-display text-xl font-bold"><ShieldCheck className="size-5 text-brand-ink" />Product passport</h2>
          {pass ? <StatusBadge badge={pass.status_badge} size="lg" /> : <StatusBadge badge={null} />}
        </div>
        {pass && <Verdict pass={pass} recalls={recalls} />}
        {passport.loading ? (
          <div className="p-8"><Skeleton className="h-40 w-full" /></div>
        ) : !pass ? (
          <p className="p-8 text-muted">This product has not been screened yet.</p>
        ) : (
          <div className="grid gap-8 p-6 sm:p-8 lg:grid-cols-[auto_1fr]">
            <div className="flex flex-col items-center gap-3">
              <TrustRing score={pass.trust_score} size={176} />
              <p className="text-xs text-muted">Version {pass.version} · {new Date(pass.verified_at).toLocaleDateString()}</p>
            </div>
            <div className="space-y-6">
              <dl className="grid gap-3 sm:grid-cols-3">
                {[
                  ['Recalls', pass.recall_component, recalls.length ? `${recalls.length} found` : 'No notice names it'],
                  ['Certificates', pass.certification_component, p.certifications.length ? `${p.certifications.length} on record` : 'None on record'],
                  ['Hazard', pass.hazard_component, pass.hazard?.label ? `${pass.hazard.label} hazard` : 'Not yet scored'],
                ].map(([k, v, text]) => (
                  <div key={k as string} className="rounded-2xl border border-line bg-white p-4">
                    <dt className="text-[11px] font-semibold uppercase tracking-wider text-muted">{k}</dt>
                    <dd className="mt-1 font-semibold">{text}</dd>
                    {v !== null && (
                      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-neutral-tint">
                        <motion.div className="h-full rounded-full" style={{ background: scoreTone(v as number) }} initial={{ width: 0 }} animate={{ width: `${v}%` }} transition={{ duration: 1 }} />
                      </div>
                    )}
                  </div>
                ))}
              </dl>

              {pass.tier === 1 && (
                <div className="rounded-2xl border border-gold/40 bg-gold-tint/60 p-5">
                  <p className="font-semibold">Identified, but not checked yet</p>
                  <p className="mt-1 text-sm text-muted">
                    No recall notice names this product, but no certificate, report or review has been checked either, so it has no trust score yet.
                    It is re-screened automatically as evidence arrives{canContribute ? ': a review from you would be the first.' : '.'}
                  </p>
                </div>
              )}
              {recalls.map((r) => (
                <motion.div key={r.recall_id} initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="relative overflow-hidden rounded-2xl border border-danger/30 bg-danger-tint p-5">
                  <span className="absolute -right-6 -top-6 size-24 rounded-full bg-danger/10" />
                  <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-danger"><AlertOctagon className="size-4" />Recall · {VERDICT[r.verdict] ?? r.verdict}</p>
                  <p className="mt-2 font-semibold">{cleanTitle(r.title)}</p>
                  {r.hazard && <p className="mt-2 text-sm">{r.hazard}</p>}
                  {r.remedy && <p className="mt-2 text-sm"><span className="font-semibold">What to do:</span> {r.remedy}</p>}
                  {r.url && <a className="mt-3 inline-block text-sm font-semibold text-danger underline" href={r.url} target="_blank" rel="noreferrer noopener">Read the official notice</a>}
                </motion.div>
              ))}

              {p.certifications.length > 0 && (
                <ul className="flex flex-wrap gap-2">
                  {p.certifications.map((c) => (
                    <li key={c.scheme + c.identifier} className={`chip ${CERT[c.status] ?? 'bg-neutral-tint text-muted'}`}>
                      <BadgeCheck className="size-3.5" />{c.scheme.toUpperCase().replace('_', ' ')} {c.identifier} · {c.status.replace('_', ' ')}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>

      <div className="mt-8"><Research slug={p.slug} onRated={rated} /></div>
      <Assistant slug={p.slug} name={p.name} />

      {pass?.hazard && (
        <section className="mt-8 grid gap-8 lg:grid-cols-[1.4fr_1fr]">
          <div className="card">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-display text-xl font-bold">Hazard scores</h2>
              <p className={`chip ${stub ? 'bg-neutral-tint text-muted' : 'bg-action-tint text-action'}`}>
                <Bot className="size-3.5" />{stub ? 'Keyword placeholder, not AI' : `Scored by ${pass.hazard.model_code}`}
              </p>
            </div>
            <p className="mt-1 text-sm text-muted">Higher means more hazardous. Open a score to see the evidence it rests on.</p>
            <ul className="mt-2 divide-y divide-line">
              {pass.hazard.dimensions.map((d, i) => <DimensionRow key={d.code} d={d} index={i} />)}
            </ul>
          </div>
          <div className="card h-fit">
            <h2 className="flex items-center gap-2 font-display text-xl font-bold"><History className="size-5 text-brand-ink" />Passport history</h2>
            <ol className="relative mt-5 space-y-5 border-l border-line pl-6">
              {pass.history.map((h, i) => (
                <motion.li key={h.version} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} className="relative">
                  <span className={`absolute -left-[31px] top-1 size-3.5 rounded-full ring-4 ring-white ${i === 0 ? 'bg-brand-ink' : 'bg-line'}`} />
                  <p className="text-sm font-semibold">Version {h.version} {i === 0 && <span className="chip ml-1 bg-brand-tint !py-0 text-brand-ink">current</span>}</p>
                  <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                    <StatusBadge badge={h.status_badge} />
                    {h.trust_score !== null && <span>trust {Math.round(h.trust_score)}</span>}
                    <span>{new Date(h.verified_at).toLocaleString()}</span>
                  </p>
                </motion.li>
              ))}
            </ol>
            {canContribute && (
              <Link to="/rewards" className="mt-6 flex items-center gap-2 text-sm font-semibold text-action"><FileText className="size-4" />Get the full report with TelCoins</Link>
            )}
          </div>
        </section>
      )}

      <div className="mt-8"><Alternatives slug={p.slug} category={p.category} /></div>

      <section aria-labelledby="reviews" className="mt-12 grid gap-8 lg:grid-cols-[1fr_24rem]">
        <div>
          <h2 id="reviews" className="font-display text-2xl font-bold">Reviews</h2>
          {reviews.loading ? (
            <div className="mt-4 space-y-4">{[0, 1].map((i) => <Skeleton key={i} className="h-28 w-full rounded-3xl" />)}</div>
          ) : reviews.items.length === 0 ? (
            <div className="mt-4"><EmptyState icon={MessageSquarePlus} title="No reviews yet">The first review of a product earns a 30 TelCoin bonus.</EmptyState></div>
          ) : (
            <ul className="mt-4 space-y-4">
              <AnimatePresence initial={false}>
                {reviews.items.map((r) => (
                  <motion.li key={r.id} layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span className="grid size-9 place-items-center rounded-full bg-panel text-xs font-bold text-muted">{(r.author ?? 'M')[0]}</span>
                        <div>
                          <p className="text-sm font-semibold">{r.author ?? 'Marketplace review'}</p>
                          <p className="text-xs text-muted">{new Date(r.created_at).toLocaleDateString()}</p>
                        </div>
                      </div>
                      <Stars rating={r.rating} />
                    </div>
                    {r.title && <p className="mt-3 font-semibold">{r.title}</p>}
                    <p className="mt-1 text-sm text-muted">{r.body}</p>
                    {r.helpful_count > 0 && <p className="mt-3 flex items-center gap-1 text-xs text-muted"><ThumbsUp className="size-3.5" />{r.helpful_count} found this helpful</p>}
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          )}
          <Pager hasMore={reviews.hasMore} loading={reviews.loadingMore} onMore={reviews.more} shown={reviews.items.length} />
        </div>
        <aside className="space-y-6">
          {canContribute ? (
            <Contribute slug={p.slug} onReview={() => { void reviews.reload(); setTimeout(() => void passport.reload(), 2500); }} />
          ) : (
            <div className="card bg-gradient-to-br from-brand-tint to-white">
              <p className="font-display text-lg font-bold text-brand-ink">Own this product?</p>
              <p className="mt-2 text-sm text-muted">Verified members can review it, report hazards, suggest corrections and earn TelCoins.</p>
              <Link to={me ? '/verify' : '/sign-up'} className="btn mt-5 w-full">{me ? 'Finish verification' : 'Create your TelcronID'}</Link>
            </div>
          )}
          {product.error && <Notice tone="error">{product.error}</Notice>}
        </aside>
      </section>
    </div>
  );
}
