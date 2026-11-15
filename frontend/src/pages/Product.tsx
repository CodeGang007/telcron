import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Notice, Stars, StatusBadge } from '../components/ui';
import { api, explain, post, type Dimension, type Passport, type ProductDetail, type Review } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useLoad } from '../lib/useLoad';

const HAZARD_LABEL: Record<string, string> = { low: 'Low hazard', medium: 'Medium hazard', high: 'High hazard' };
const VERDICT: Record<string, string> = { match: 'Matches this product', possible: 'May match this product' };

function DimensionRow({ d }: { d: Dimension }) {
  const scored = d.status === 'scored' && d.score !== null;
  const tone = !scored ? 'bg-line' : d.score! >= 60 ? 'bg-danger' : d.score! >= 30 ? 'bg-warn' : 'bg-ok';
  return (
    <li className="border-b border-line py-4 last:border-0">
      <div className="flex items-baseline justify-between gap-4">
        <p className="font-medium">{d.name}</p>
        <p className="text-sm text-muted">{scored ? `${Math.round(d.score!)} / 100` : 'Not enough evidence'}</p>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-neutral-tint" aria-hidden>
        <div className={`h-full ${tone}`} style={{ width: `${scored ? Math.max(2, d.score!) : 0}%` }} />
      </div>
      {d.justification && <p className="mt-2 text-sm text-muted">{d.justification}</p>}
      {d.citations.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer text-action">Evidence ({d.citations.length})</summary>
          <ul className="mt-2 space-y-2">
            {d.citations.map((c) => (
              <li key={c.id} className="rounded-xl bg-panel px-3 py-2 text-muted">
                <span className="mr-2 text-xs font-semibold uppercase text-ink">{c.kind.replace('_', ' ')}</span>
                {c.excerpt}
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}

function ReviewForm({ slug, onDone }: { slug: string; onDone: () => void }) {
  const [rating, setRating] = useState(5);
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const r = await post<{ coins_pending: number }>(`/products/${slug}/reviews`, { rating, body });
      setMsg({ tone: 'ok', text: `Review posted. ${r.coins_pending} TelCoins are pending while we check it.` });
      setBody('');
      onDone();
    } catch (err) {
      setMsg({ tone: 'error', text: explain(err) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="card space-y-4">
      <h3 className="font-semibold">Write a review</h3>
      <label className="block text-sm">
        Rating
        <select className="field mt-1" value={rating} onChange={(e) => setRating(Number(e.target.value))}>
          {[5, 4, 3, 2, 1].map((n) => (
            <option key={n} value={n}>
              {n} out of 5
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        Your experience (at least 20 characters)
        <textarea
          className="field mt-1 min-h-28"
          required
          minLength={20}
          maxLength={5000}
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
      </label>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <button className="btn" disabled={busy}>
        {busy ? 'Posting…' : 'Post review'}
      </button>
    </form>
  );
}

export function Product() {
  const { slug = '' } = useParams();
  const { me } = useAuth();
  const product = useLoad(() => api<ProductDetail>(`/products/${slug}`), [slug]);
  const passport = useLoad(() => api<Passport>(`/products/${slug}/passport`).catch(() => null), [slug]);
  const reviews = useLoad(() => api<Review[]>(`/products/${slug}/reviews`), [slug]);
  const [saved, setSaved] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null);

  if (product.loading) return <div className="container-page py-12"><Notice>Loading product…</Notice></div>;
  if (product.error || !product.data)
    return (
      <div className="container-page py-12">
        <Notice tone="error">We could not find that product. <Link className="underline" to="/search">Search again</Link>.</Notice>
      </div>
    );
  const p = product.data;
  const pass = passport.data;
  const canContribute = !!me && me.verification_level >= 1;

  const save = async () => {
    try {
      await post('/wallet/items', { product_id: p.slug });
      setSaved({ tone: 'ok', text: 'Saved to your Digital Wallet. We will alert you if its passport changes.' });
    } catch (e) {
      setSaved({ tone: 'error', text: explain(e) });
    }
  };

  return (
    <div className="container-page py-12">
      <p className="eyebrow">{p.category}</p>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold sm:text-4xl">{p.name}</h1>
          <p className="mt-2 text-muted">{[p.brand, p.model_number].filter(Boolean).join(' · ')}</p>
        </div>
        {canContribute ? (
          <button className="btn" onClick={save}>Save to wallet</button>
        ) : (
          <Link className="btn-ghost" to="/sign-in">Sign in to save</Link>
        )}
      </div>
      {saved && <div className="mt-4"><Notice tone={saved.tone}>{saved.text}</Notice></div>}

      <section aria-labelledby="passport" className="mt-10 rounded-3xl bg-panel p-6 sm:p-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 id="passport" className="text-2xl font-semibold">Product passport</h2>
          <StatusBadge badge={pass?.status_badge ?? null} />
        </div>
        {!pass ? (
          <p className="mt-4 text-muted">This product has not been screened yet.</p>
        ) : (
          <>
            <dl className="mt-6 grid gap-4 sm:grid-cols-4">
              {[
                ['Trust score', pass.trust_score === null ? '—' : `${Math.round(pass.trust_score)} / 100`],
                ['Recalls', pass.recall_matches.length ? `${pass.recall_matches.length} found` : 'None found'],
                ['Hazard', pass.hazard?.label ? HAZARD_LABEL[pass.hazard.label] : 'Not enough evidence'],
                ['Version', `v${pass.version} · ${new Date(pass.verified_at).toLocaleDateString()}`],
              ].map(([k, v]) => (
                <div key={k} className="rounded-2xl bg-white p-4">
                  <dt className="text-xs uppercase tracking-wide text-muted">{k}</dt>
                  <dd className="mt-1 font-semibold">{v}</dd>
                </div>
              ))}
            </dl>

            {pass.recall_matches.map((r) => (
              <div key={r.recall_id} className="mt-6 rounded-2xl border border-danger bg-danger-tint p-5">
                <p className="text-xs font-semibold uppercase text-danger">Recall · {VERDICT[r.verdict] ?? r.verdict}</p>
                <p className="mt-1 font-semibold">{r.title}</p>
                {r.hazard && <p className="mt-2 text-sm">{r.hazard}</p>}
                {r.remedy && <p className="mt-2 text-sm"><span className="font-semibold">What to do:</span> {r.remedy}</p>}
              </div>
            ))}

            {p.certifications.length > 0 && (
              <div className="mt-6">
                <h3 className="font-semibold">Certificates</h3>
                <ul className="mt-2 flex flex-wrap gap-2">
                  {p.certifications.map((c) => (
                    <li key={c.identifier} className="rounded-full bg-white px-4 py-2 text-sm">
                      {c.scheme} {c.identifier} · <span className="font-medium">{c.status}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {pass.hazard && (
              <div className="mt-8 rounded-2xl bg-white p-5">
                <h3 className="font-semibold">Hazard scores</h3>
                <p className="mt-1 text-sm text-muted">Higher means more hazardous. Each score lists the evidence it rests on.</p>
                <ul className="mt-2">
                  {pass.hazard.dimensions.map((d) => (
                    <DimensionRow key={d.code} d={d} />
                  ))}
                </ul>
                {pass.hazard.model_code.startsWith('stub') && (
                  <p className="mt-4 text-xs text-muted">
                    Development build: these scores come from a keyword placeholder, not the AI model.
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </section>

      <section aria-labelledby="reviews" className="mt-12 grid gap-8 lg:grid-cols-[1fr_22rem]">
        <div>
          <h2 id="reviews" className="text-2xl font-semibold">Reviews</h2>
          {reviews.data?.length === 0 && <p className="mt-4 text-muted">No reviews yet. The first review earns a bonus.</p>}
          <ul className="mt-4 space-y-4">
            {reviews.data?.map((r) => (
              <li key={r.id} className="card">
                <div className="flex items-center justify-between gap-3">
                  <Stars rating={r.rating} />
                  <span className="text-xs text-muted">
                    {r.author ?? 'Marketplace review'} · {new Date(r.created_at).toLocaleDateString()}
                  </span>
                </div>
                {r.title && <p className="mt-2 font-semibold">{r.title}</p>}
                <p className="mt-1 text-sm text-muted">{r.body}</p>
              </li>
            ))}
          </ul>
        </div>
        <aside>
          {canContribute ? (
            <ReviewForm
              slug={p.slug}
              onDone={() => {
                void reviews.reload();
                // The re-screen runs in the background; pick up the new passport shortly after.
                setTimeout(() => void passport.reload(), 2500);
              }}
            />
          ) : (
            <div className="card bg-brand-tint">
              <p className="font-semibold text-brand-ink">Own this product?</p>
              <p className="mt-2 text-sm text-muted">
                Verified members can review it, flag hazards and earn TelCoins.
              </p>
              <Link to={me ? '/verify' : '/sign-up'} className="btn mt-4">
                {me ? 'Finish verification' : 'Create your TelcronID'}
              </Link>
            </div>
          )}
        </aside>
      </section>
    </div>
  );
}
