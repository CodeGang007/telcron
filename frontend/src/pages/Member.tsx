import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Notice, PageTitle, StatusBadge } from '../components/ui';
import { api, explain } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useLoad } from '../lib/useLoad';

/** Wraps a members-only page: signed out, or not yet Level 1, gets a way forward, not an error. */
function Gate({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <Notice>Loading…</Notice>;
  if (!me)
    return (
      <div className="card bg-brand-tint">
        <p className="font-semibold text-brand-ink">Sign in to continue</p>
        <p className="mt-2 text-sm text-muted">This page is part of your TelcronID.</p>
        <div className="mt-4 flex gap-3">
          <Link to="/sign-in" className="btn">Sign In</Link>
          <Link to="/sign-up" className="btn-ghost">Create account</Link>
        </div>
      </div>
    );
  if (me.verification_level < 1)
    return <Notice>Confirm your email and phone to use this page. Resending codes is not available yet.</Notice>;
  return <>{children}</>;
}

type WalletItem = {
  id: string; slug: string; name: string; brand: string | null;
  status: string; status_badge: string | null; trust_score: number | null; passport_changed: boolean;
};
type Alert = { id: string; severity: string; title: string; summary: string | null; product_slug: string; created_at: string };

function WalletBody() {
  const items = useLoad(() => api<WalletItem[]>('/wallet/items'), []);
  const alerts = useLoad(() => api<Alert[]>('/alerts'), []);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const remove = async (id: string) => {
    setRemoveError(null);
    try {
      await api(`/wallet/items/${id}`, { method: 'DELETE' });
      await items.reload();
    } catch (e) {
      setRemoveError(explain(e));
    }
  };
  return (
    <div className="grid gap-10 lg:grid-cols-[1fr_22rem]">
      <section aria-label="Saved products">
        {items.error && <Notice tone="error">{items.error}</Notice>}
        {removeError && <Notice tone="error">{removeError}</Notice>}
        {items.data?.length === 0 && (
          <Notice>
            Nothing saved yet. <Link className="text-action underline" to="/search">Find a product</Link> you own and save it.
          </Notice>
        )}
        <ul className="space-y-4">
          {items.data?.map((i) => (
            <li key={i.id} className="card flex flex-wrap items-center justify-between gap-4">
              <div>
                <Link to={`/products/${i.slug}`} className="font-semibold hover:text-action">{i.name}</Link>
                <p className="text-sm text-muted">{i.brand}</p>
                {i.passport_changed && <p className="mt-1 text-sm font-medium text-warn">Passport changed since you saved it</p>}
                {i.status === 'pending_verification' && <p className="mt-1 text-sm text-muted">Awaiting ownership check; no alerts yet</p>}
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge badge={i.status_badge} />
                <button className="btn-ghost !px-4 !py-2" onClick={() => remove(i.id)}>Remove</button>
              </div>
            </li>
          ))}
        </ul>
      </section>
      <aside aria-label="Risk alerts">
        <h2 className="text-xl font-semibold">Risk alerts</h2>
        {alerts.data?.length === 0 && <p className="mt-3 text-sm text-muted">No alerts. We watch your saved products for you.</p>}
        <ul className="mt-3 space-y-3">
          {alerts.data?.map((a) => (
            <li key={a.id} className="rounded-2xl border border-danger bg-danger-tint p-4 text-sm">
              <p className="text-xs font-semibold uppercase text-danger">{a.severity}</p>
              <Link to={`/products/${a.product_slug}`} className="mt-1 block font-semibold">{a.title}</Link>
              <p className="mt-1 text-muted">{new Date(a.created_at).toLocaleString()}</p>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

export function Wallet() {
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Digital Wallet" title="Products you own">
        Save what you own and Telcron alerts you when a recall, certificate or hazard score changes.
      </PageTitle>
      <Gate><WalletBody /></Gate>
    </div>
  );
}

type Coins = {
  confirmed: number; pending: number; frozen: number; lifetime_earned: number;
  level: { level: number; title: string; next_title: string | null; next_at: number | null } | null;
};
type Entry = { id: string; entry_type: string; amount: number; status: string; rule_code: string | null; created_at: string };
const RULES: Record<string, string> = {
  level1_verified: 'Reached Level 1', level2_verified: 'Reached Level 2', review: 'Review',
  first_reviewer: 'First review of a product', photo: 'Photo', hazard_flag_confirmed: 'Hazard flag confirmed',
  fact_verification: 'Fact verified', login_streak: 'Daily sign-in', login_streak_7plus: 'Sign-in streak',
  referral: 'Referral',
};
const ENTRY: Record<string, string> = {
  level_bonus: 'Level bonus', spend: 'Spent', clawback: 'Taken back', adjustment: 'Adjustment', refund: 'Refund',
};
const STATUS: Record<string, string> = { pending: 'Pending check', confirmed: 'Confirmed', frozen: 'On hold', reversed: 'Reversed' };

function RewardsBody() {
  const coins = useLoad(() => api<Coins>('/coins'), []);
  const history = useLoad(() => api<Entry[]>('/coins/history'), []);
  const c = coins.data;
  return (
    <>
      {coins.error && <Notice tone="error">{coins.error}</Notice>}
      {c && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-3xl bg-brand p-6 text-white">
            <p className="text-sm opacity-80">TelCoins</p>
            <p className="mt-1 text-4xl font-semibold">{c.confirmed.toLocaleString()}</p>
            <p className="mt-2 text-sm opacity-80">{c.pending.toLocaleString()} pending</p>
          </div>
          <div className="card">
            <p className="text-sm text-muted">Level</p>
            <p className="mt-1 text-2xl font-semibold">{c.level?.title ?? '—'}</p>
            {c.level?.next_at != null && (
              <p className="mt-2 text-sm text-muted">
                {(c.level.next_at - c.lifetime_earned).toLocaleString()} more to reach {c.level.next_title}
              </p>
            )}
          </div>
          <div className="card">
            <p className="text-sm text-muted">Earned in total</p>
            <p className="mt-1 text-2xl font-semibold">{c.lifetime_earned.toLocaleString()}</p>
            {c.frozen > 0 && <p className="mt-2 text-sm text-warn">{c.frozen.toLocaleString()} on hold for review</p>}
          </div>
        </div>
      )}
      <h2 className="mt-10 text-xl font-semibold">History</h2>
      {history.data?.length === 0 && <p className="mt-3 text-sm text-muted">Nothing yet. Review a product you own to earn your first coins.</p>}
      <ul className="mt-3 divide-y divide-line rounded-3xl border border-line">
        {history.data?.map((e) => (
          <li key={e.id} className="flex items-center justify-between gap-4 px-5 py-4 text-sm">
            <div>
              <p className="font-medium">{RULES[e.rule_code ?? ''] ?? ENTRY[e.entry_type] ?? e.entry_type}</p>
              <p className="text-muted">{new Date(e.created_at).toLocaleString()} · {STATUS[e.status] ?? e.status}</p>
            </div>
            <p className="font-semibold">{e.amount < 0 ? '−' : '+'}{Math.abs(e.amount)}</p>
          </li>
        ))}
      </ul>
    </>
  );
}

type Contributions = {
  flags: { id: string; status: string; description: string | null; resolution_note: string | null; product_slug: string; product_name: string; created_at: string }[];
  fact_reports: { id: string; status: string; attribute: string; proposed_value: string | null; product_slug: string; product_name: string; created_at: string }[];
};
const DECISION: Record<string, string> = { pending: 'Waiting for review', confirmed: 'Confirmed', accepted: 'Accepted', rejected: 'Not accepted' };

function ContributionsBody() {
  const c = useLoad(() => api<Contributions>('/contributions'), []);
  const rows = [
    ...(c.data?.flags ?? []).map((f) => ({ ...f, kind: 'Hazard report', text: f.description })),
    ...(c.data?.fact_reports ?? []).map((r) => ({ ...r, kind: 'Correction', text: `${r.attribute.replace(/_/g, ' ')} → ${r.proposed_value ?? 'confirmed'}`, resolution_note: null })),
  ].sort((a, b) => b.created_at.localeCompare(a.created_at));
  if (!c.data || rows.length === 0) return null;
  return (
    <section aria-labelledby="contributions">
      <h2 id="contributions" className="mt-10 text-xl font-semibold">Your reports and corrections</h2>
      <ul className="mt-3 divide-y divide-line rounded-3xl border border-line">
        {rows.map((r) => (
          <li key={r.id} className="px-5 py-4 text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <Link to={`/products/${r.product_slug}`} className="font-medium hover:text-action">{r.kind} · {r.product_name}</Link>
              <span className={r.status === 'pending' ? 'text-muted' : r.status === 'rejected' ? 'text-warn' : 'font-medium text-ok'}>{DECISION[r.status] ?? r.status}</span>
            </div>
            <p className="mt-1 text-muted">{r.text}</p>
            {r.resolution_note && <p className="mt-1 text-xs text-muted">Reviewer: {r.resolution_note}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Rewards() {
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Telcron Rewards" title="Your TelCoins">
        Coins are confirmed a few minutes after a contribution, once it has been checked. They cannot be exchanged for money.
      </PageTitle>
      <Gate><RewardsBody /><ContributionsBody /></Gate>
    </div>
  );
}

export function Leaderboard() {
  const rows = useLoad(() => api<{ rank: number; display_name: string; coins: number }[]>('/leaderboard'), []);
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Community" title="Top contributors this month" />
      {rows.error && <Notice tone="error">{rows.error}</Notice>}
      {rows.data?.length === 0 && <Notice>No confirmed contributions yet this month. Yours could be the first.</Notice>}
      <ol className="divide-y divide-line rounded-3xl border border-line">
        {rows.data?.map((r) => (
          <li key={r.rank} className="flex items-center justify-between px-5 py-4">
            <span><span className="mr-4 inline-block w-6 font-semibold text-brand-ink">{r.rank}</span>{r.display_name}</span>
            <span className="font-semibold">{r.coins.toLocaleString()}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
