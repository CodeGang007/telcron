import { Flag, MessageSquarePlus, PencilLine, Star, ThumbsUp } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { ApiError, explain, post, type Review } from '../lib/api';
import { useAuth } from '../lib/auth';
import { coinsChanged } from '../lib/coins';
import { FactForm, FlagForm } from './Contribute';
import { EmptyState, Notice, Pager, Skeleton, Stars } from './ui';

type Paged = {
  items: Review[]; loading: boolean; loadingMore: boolean; hasMore: boolean; error: string | null;
  more: () => Promise<void>; reload: () => Promise<void>;
};

// Reviews this member voted helpful in this browser. The review list does not say yet whether the
// caller voted (backend request in DEF-031); until it does, this keeps the vote visible after a reload.
const VOTES = 'telcron.helpful:';
function readVotes(userId: string): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(VOTES + userId) ?? '[]') as string[]);
  } catch {
    return new Set();
  }
}
function rememberVote(userId: string, reviewId: string) {
  try {
    const votes = readVotes(userId).add(reviewId);
    localStorage.setItem(VOTES + userId, JSON.stringify([...votes].slice(-500)));
  } catch {
    // Storage full or disabled: the vote still counted on the server.
  }
}

/** "Helpful" on someone else's review (journey 4, DEF-031). The server counts one vote per member,
    so a repeat is harmless and never counted twice. */
function Helpful({ review }: { review: Review }) {
  const { me } = useAuth();
  const remembered = !!me && readVotes(me.id).has(review.id);
  const [voted, setVoted] = useState(!!review.voted || remembered);
  const [added, setAdded] = useState(0);
  const [own, setOwn] = useState(!!review.mine);
  const [busy, setBusy] = useState(false);
  const count = review.helpful_count + added;
  const counted = count > 0 && <span>{count} found this helpful</span>;

  if (!review.author || own) return counted ? <p className="mt-3 flex items-center gap-1 text-xs text-muted"><ThumbsUp className="size-3.5" />{counted}</p> : null;
  if (!me || me.verification_level < 1)
    return (
      <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        {counted}
        <Link to={me ? '/verify' : '/sign-in'} className="font-semibold text-action hover:underline">{me ? 'Confirm your email to vote helpful' : 'Sign in to vote helpful'}</Link>
      </p>
    );

  const vote = async () => {
    setBusy(true);
    try {
      await post(`/reviews/${review.id}/helpful`);
      rememberVote(me.id, review.id);
      setVoted(true);
      setAdded(1);
    } catch (e) {
      if (e instanceof ApiError && e.code === 'own_review') setOwn(true);
      toast.error(explain(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted">
      <button
        onClick={vote}
        disabled={busy || voted}
        aria-pressed={voted}
        className={`inline-flex min-h-11 items-center gap-1.5 rounded-full border px-4 font-semibold transition ${voted ? 'border-action/30 bg-action-tint text-action' : 'border-line bg-white text-ink hover:border-action hover:text-action'}`}
      >
        <ThumbsUp className={`size-4 ${voted ? 'fill-action/20' : ''}`} />{voted ? 'You found this helpful' : 'Helpful'}
      </button>
      {counted}
    </div>
  );
}

export function ReviewList({ reviews }: { reviews: Paged }) {
  if (reviews.loading) return <div className="mt-4 space-y-4">{[0, 1].map((i) => <Skeleton key={i} className="h-28 w-full rounded-3xl" />)}</div>;
  if (reviews.error && reviews.items.length === 0)
    return <div className="mt-4"><Notice tone="error">{reviews.error} <button className="font-semibold underline" onClick={() => void reviews.reload()}>Try again</button></Notice></div>;
  if (reviews.items.length === 0)
    return <div className="mt-4"><EmptyState icon={MessageSquarePlus} title="No reviews yet">The first review of a product earns a 30 TelCoin bonus.</EmptyState></div>;
  return (
    <>
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
              <Helpful review={r} />
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
      <Pager hasMore={reviews.hasMore} loading={reviews.loadingMore} onMore={reviews.more} shown={reviews.items.length} />
    </>
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
      coinsChanged();
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

export function ContributeTabs({ slug, onReview }: { slug: string; onReview: () => void }) {
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
