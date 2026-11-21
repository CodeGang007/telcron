import confetti from 'canvas-confetti';
import {
  Award,
  BadgeCheck,
  Camera,
  Check,
  Coins,
  Crown,
  FileText,
  Flame,
  Gem,
  IdCard,
  Lock,
  Medal,
  MessageSquare,
  ShieldAlert,
  ShoppingBag,
  Sparkles,
  Star,
  Trophy,
  UserCheck,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { motion } from 'motion/react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Gate } from '../components/Gate';
import { AnimatedNumber, Notice, PageTitle, Pager, Skeleton, stagger } from '../components/ui';
import { api, explain, post } from '../lib/api';
import { tokenHex } from '../lib/tokens';
import { coinsChanged } from '../lib/coins';
import { useLoad } from '../lib/useLoad';
import { usePaged } from '../lib/usePaged';

type Overview = {
  balance: { confirmed: number; pending: number; frozen: number; lifetime_earned: number };
  level: number;
  levels: { level: number; title: string; min: number; bonus_pct: number; perks: string[] }[];
  streak_days: number;
  rank: number | null;
  ranked: number;
  ways_to_earn: { code: string; amount: number; icon: string; label: string; capped: boolean }[];
  badges: { code: string; name: string; earned_at: string | null }[];
  store: { code: string; name: string; cost: number; kind: string; needs_product: boolean }[];
};
type Entry = { id: string; entry_type: string; amount: number; status: string; rule_code: string | null; created_at: string };
type Contributions = {
  flags: { id: string; status: string; description: string | null; resolution_note: string | null; product_slug: string; product_name: string; created_at: string }[];
  fact_reports: { id: string; status: string; attribute: string; proposed_value: string | null; product_slug: string; product_name: string; created_at: string }[];
};

const ICONS: Record<string, LucideIcon> = {
  'message-square': MessageSquare, sparkles: Sparkles, camera: Camera, 'shield-alert': ShieldAlert,
  'badge-check': BadgeCheck, flame: Flame, users: Users, 'user-check': UserCheck, 'id-card': IdCard, coins: Coins,
};
const LEVEL_ICON: LucideIcon[] = [Star, Medal, Award, Gem, Crown];
const BADGE_ICON: Record<string, LucideIcon> = { inspector: Medal, analyst: Award, expert: Gem, master: Crown, beta_tester: Sparkles, identity_verified: IdCard };
const RULES: Record<string, string> = {
  level1_verified: 'Reached Level 1', level2_verified: 'Reached Level 2', review: 'Review',
  first_reviewer: 'First review of a product', photo: 'Photo', hazard_flag_confirmed: 'Hazard flag confirmed',
  fact_verification: 'Fact verified', login_streak: 'Daily sign-in', login_streak_7plus: 'Sign-in streak', referral: 'Referral',
};
const ENTRY: Record<string, string> = { level_bonus: 'Level bonus', spend: 'Spent in the store', clawback: 'Taken back', adjustment: 'Adjustment', refund: 'Refund' };
const STATUS: Record<string, string> = { pending: 'Pending check', confirmed: 'Confirmed', frozen: 'On hold', reversed: 'Reversed' };
const DECISION: Record<string, string> = { pending: 'Waiting for review', confirmed: 'Confirmed', accepted: 'Accepted', rejected: 'Not accepted' };
const STORE_ICON: Record<string, LucideIcon> = { pdf_report: FileText, watchlist_slots: ShieldAlert, feature_access: Sparkles, rate_limit_boost: Flame, data_export: FileText, invoice_discount: Coins };

function LevelRing({ pct, children }: { pct: number; children: React.ReactNode }) {
  const size = 132, stroke = 10, r = (size - stroke) / 2, c = 2 * Math.PI * r;
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" className="stroke-white/15" strokeWidth={stroke} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-gold)" strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c}
          initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - pct) }} transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center">{children}</div>
    </div>
  );
}

function Hero({ o }: { o: Overview }) {
  const current = o.levels.find((l) => l.level === o.level) ?? o.levels[0] ?? { level: 1, title: 'Novice', min: 0, bonus_pct: 0, perks: [] };
  const next = o.levels.find((l) => l.level === o.level + 1);
  const pct = next ? (o.balance.lifetime_earned - current.min) / (next.min - current.min) : 1;
  const Icon = LEVEL_ICON[(o.level - 1) % LEVEL_ICON.length] ?? Star;
  return (
    <section className="relative overflow-hidden rounded-[2rem] bg-night p-8 text-white shadow-lift sm:p-10">
      <div className="bg-grid absolute inset-0 opacity-70" />
      <motion.div className="absolute -right-20 -top-24 size-80 rounded-full bg-gold/30 blur-3xl" animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 8, repeat: Infinity }} />
      <motion.div className="absolute -bottom-24 left-10 size-72 rounded-full bg-brand-ink/40 blur-3xl" animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 10, repeat: Infinity }} />
      <div className="relative grid items-center gap-10 lg:grid-cols-[1fr_auto]">
        <div>
          <p className="text-sm font-medium text-white/60">Spendable TelCoins</p>
          <p className="mt-2 flex items-center gap-3 font-display text-6xl font-extrabold tracking-tight sm:text-7xl">
            <motion.span initial={{ rotate: -30, scale: 0.6 }} animate={{ rotate: 0, scale: 1 }} transition={{ type: 'spring', stiffness: 200 }} className="grid size-14 place-items-center rounded-full bg-gradient-to-br from-gold-light to-gold-deep shadow-[0_0_40px] shadow-gold/50">
              <Coins className="size-8 text-gold-dark" />
            </motion.span>
            <AnimatedNumber value={o.balance.confirmed} />
          </p>
          <div className="mt-5 flex flex-wrap gap-2 text-sm">
            <span className="glass chip !py-1.5 text-white/90">{o.balance.pending.toLocaleString()} pending</span>
            {o.balance.frozen > 0 && <span className="chip bg-warn/90 !py-1.5 text-white">{o.balance.frozen.toLocaleString()} on hold</span>}
            <span className="glass chip !py-1.5 text-white/90">{o.balance.lifetime_earned.toLocaleString()} earned in total</span>
          </div>
          <div className="mt-8 grid max-w-md grid-cols-2 gap-3">
            <div className="glass rounded-2xl p-4">
              <p className="flex items-center gap-2 text-xs text-white/60"><Flame className="size-4 text-flame" />Sign-in streak</p>
              <p className="mt-1 font-display text-2xl font-bold">{o.streak_days} {o.streak_days === 1 ? 'day' : 'days'}</p>
              <p className="text-xs text-white/50">{o.streak_days >= 7 ? 'Double coins every day' : `${7 - o.streak_days} more for double coins`}</p>
            </div>
            <div className="glass rounded-2xl p-4">
              <p className="flex items-center gap-2 text-xs text-white/60"><Trophy className="size-4 text-gold" />This month</p>
              <p className="mt-1 font-display text-2xl font-bold">{o.rank ? `#${o.rank}` : 'Unranked'}</p>
              <p className="text-xs text-white/50">{o.rank ? `of ${o.ranked} contributors` : 'Confirmed coins put you on the board'}</p>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-center text-center">
          <LevelRing pct={Math.max(0.02, Math.min(1, pct))}>
            <div>
              <Icon className="mx-auto size-8 text-gold" />
              <p className="mt-1 font-display text-lg font-bold">{current.title}</p>
              <p className="text-[11px] text-white/60">Level {o.level}</p>
            </div>
          </LevelRing>
          <p className="mt-4 max-w-[14rem] text-sm text-white/70">
            {next ? <><span className="font-semibold text-white">{(next.min - o.balance.lifetime_earned).toLocaleString()}</span> more to reach {next.title}</> : 'Top level reached'}
          </p>
          {current.bonus_pct > 0 && <p className="mt-1 text-xs text-gold">+{current.bonus_pct}% on every earn</p>}
        </div>
      </div>
    </section>
  );
}

function Store({ o, onBought }: { o: Overview; onBought: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const owned = useLoad(() => api<{ slug: string; name: string }[]>('/wallet/items'), []);
  const [chosen, setChosen] = useState<string>('');
  const buy = async (item: Overview['store'][number]) => {
    const product = item.needs_product ? chosen || owned.data?.[0]?.slug : undefined;
    if (item.needs_product && !product) return;
    setBusy(item.code);
    try {
      const r = await post<{ report: string | null }>('/redemptions', { item_code: item.code, product: product ?? null, request_id: crypto.randomUUID() });
      const colors = tokenHex('gold', 'brand-bright', 'action', 'ok');
      void confetti({ particleCount: 140, spread: 80, origin: { y: 0.7 }, ...(colors.length ? { colors } : {}) });
      toast.success(`${item.name} is yours`, { description: r.report ? 'Your report is ready.' : 'It is active on your account now.', action: r.report ? { label: 'Open', onClick: () => { window.location.href = r.report!; } } : undefined });
      onBought();
    } catch (e) {
      toast.error(explain(e));
    } finally {
      setBusy(null);
    }
  };
  return (
    <motion.ul variants={stagger.container} initial="hidden" whileInView="show" viewport={{ once: true }} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {o.store.map((item) => {
        const Icon = STORE_ICON[item.kind] ?? ShoppingBag;
        const affordable = o.balance.confirmed >= item.cost;
        return (
          <motion.li key={item.code} variants={stagger.item} className="card card-hover flex flex-col">
            <span className="grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-violet to-action text-white shadow-lg"><Icon className="size-6" /></span>
            <p className="mt-4 font-semibold">{item.name}</p>
            {item.needs_product && (
              owned.data && owned.data.length > 0 ? (
                <label className="mt-3 block text-xs text-muted">
                  For
                  <select className="field mt-1 !py-2 text-sm" value={chosen || owned.data[0]?.slug} onChange={(e) => setChosen(e.target.value)}>
                    {owned.data.map((w) => <option key={w.slug} value={w.slug}>{w.name}</option>)}
                  </select>
                </label>
              ) : (
                <p className="mt-3 text-xs text-muted">Save a product to your wallet to get its report.</p>
              )
            )}
            <div className="mt-auto flex items-center justify-between pt-5">
              <span className="chip bg-gold-tint text-gold-ink"><Coins className="size-3.5" />{item.cost.toLocaleString()}</span>
              <button className="btn btn-sm" disabled={!affordable || busy === item.code || (item.needs_product && !owned.data?.length)} onClick={() => buy(item)}>
                {busy === item.code ? 'Redeeming…' : affordable ? 'Redeem' : <><Lock className="size-3.5" />{(item.cost - o.balance.confirmed).toLocaleString()} more</>}
              </button>
            </div>
          </motion.li>
        );
      })}
    </motion.ul>
  );
}

function Contributions() {
  const c = useLoad(() => api<Contributions>('/contributions'), []);
  const rows = [
    ...(c.data?.flags ?? []).map((f) => ({ ...f, kind: 'Hazard report', text: f.description })),
    ...(c.data?.fact_reports ?? []).map((r) => ({ ...r, kind: 'Correction', text: `${r.attribute.replace(/_/g, ' ')} → ${r.proposed_value ?? 'confirmed'}`, resolution_note: null })),
  ].sort((a, b) => b.created_at.localeCompare(a.created_at));
  if (!c.data || rows.length === 0) return null;
  return (
    <section aria-labelledby="contributions" className="mt-14">
      <h2 id="contributions" className="font-display text-2xl font-bold">Your reports and corrections</h2>
      <ul className="mt-4 divide-y divide-line overflow-hidden rounded-3xl border border-line bg-white">
        {rows.map((r) => (
          <li key={r.id} className="px-5 py-4 text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <Link to={`/products/${r.product_slug}`} className="font-medium hover:text-action">{r.kind} · {r.product_name}</Link>
              <span className={`chip ${r.status === 'pending' ? 'bg-neutral-tint text-muted' : r.status === 'rejected' ? 'bg-warn-tint text-warn' : 'bg-ok-tint text-ok'}`}>{DECISION[r.status] ?? r.status}</span>
            </div>
            <p className="mt-1 text-muted">{r.text}</p>
            {r.resolution_note && <p className="mt-1 text-xs text-muted">Reviewer: {r.resolution_note}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function RewardsBody() {
  const overview = useLoad(() => api<Overview>('/rewards'), []);
  const history = usePaged<Entry>('/coins/history', 8);
  const o = overview.data;
  if (overview.error && !o)
    return <Notice tone="error">{overview.error} <button className="font-semibold underline" onClick={() => void overview.reload()}>Try again</button></Notice>;
  if (overview.loading || !o) return <div className="space-y-6"><Skeleton className="h-80 w-full rounded-[2rem]" /><Skeleton className="h-40 w-full rounded-3xl" /></div>;

  return (
    <>
      <Hero o={o} />

      <section className="mt-14">
        <h2 className="font-display text-2xl font-bold">Ways to earn</h2>
        <motion.ul variants={stagger.container} initial="hidden" whileInView="show" viewport={{ once: true }} className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {o.ways_to_earn.map((w) => {
            const Icon = ICONS[w.icon] ?? Coins;
            return (
              <motion.li key={w.code} variants={stagger.item} className="card card-hover !p-5">
                <div className="flex items-center justify-between">
                  <span className="grid size-10 place-items-center rounded-xl bg-brand-tint text-brand-ink"><Icon className="size-5" /></span>
                  <span className="font-display text-lg font-extrabold text-gold-deep">+{w.amount}</span>
                </div>
                <p className="mt-3 text-sm font-medium leading-snug">{w.label}</p>
              </motion.li>
            );
          })}
        </motion.ul>
        <p className="mt-3 text-xs text-muted">Coins are confirmed a few minutes after a contribution, once it has been checked. At most 500 a day from reviews, photos and reports. TelCoins cannot be exchanged for money.</p>
      </section>

      <section className="mt-14 grid gap-8 lg:grid-cols-2">
        <div>
          <h2 className="font-display text-2xl font-bold">Levels</h2>
          <ol className="mt-5 space-y-3">
            {o.levels.map((l, i) => {
              const Icon = LEVEL_ICON[i % LEVEL_ICON.length] ?? Star;
              const reached = o.balance.lifetime_earned >= l.min;
              return (
                <motion.li key={l.level} initial={{ opacity: 0, x: -10 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.06 }}
                  className={`flex items-center gap-4 rounded-2xl border p-4 ${l.level === o.level ? 'border-gold bg-gold-tint/60 shadow-soft' : reached ? 'border-line bg-white' : 'border-dashed border-line bg-panel/50'}`}>
                  <span className={`grid size-11 place-items-center rounded-xl ${reached ? 'bg-gradient-to-br from-gold-mid to-gold-deep text-white' : 'bg-neutral-tint text-muted'}`}><Icon className="size-5" /></span>
                  <div className="flex-1">
                    <p className="font-semibold">{l.title} {l.level === o.level && <span className="chip ml-1 bg-gold !py-0 text-white">you</span>}</p>
                    <p className="text-xs text-muted">{l.min.toLocaleString()} coins earned{l.bonus_pct > 0 ? ` · +${l.bonus_pct}% on every earn` : ''}</p>
                  </div>
                  {reached ? <Check className="size-5 text-ok" /> : <Lock className="size-4 text-muted" />}
                </motion.li>
              );
            })}
          </ol>
        </div>
        <div>
          <h2 className="font-display text-2xl font-bold">Badges</h2>
          <ul className="mt-5 grid grid-cols-3 gap-3">
            {o.badges.map((b, i) => {
              const Icon = BADGE_ICON[b.code] ?? Award;
              const earned = !!b.earned_at;
              return (
                <motion.li key={b.code} initial={{ opacity: 0, scale: 0.8 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }} transition={{ delay: i * 0.05, type: 'spring' }}
                  className={`grid place-items-center rounded-2xl border p-4 text-center ${earned ? 'border-gold/50 bg-gradient-to-b from-gold-tint to-white shadow-soft' : 'border-line bg-panel/50'}`}>
                  <span className={`grid size-14 place-items-center rounded-full ${earned ? 'bg-gradient-to-br from-gold-light to-gold-deep text-white shadow-[0_0_24px] shadow-gold/40' : 'bg-neutral-tint text-muted/50'}`}>
                    {earned ? <Icon className="size-7" /> : <Lock className="size-5" />}
                  </span>
                  <p className={`mt-2 text-xs font-semibold ${earned ? '' : 'text-muted'}`}>{b.name}</p>
                </motion.li>
              );
            })}
          </ul>
        </div>
      </section>

      <section className="mt-14">
        <h2 className="flex items-center gap-2 font-display text-2xl font-bold"><ShoppingBag className="size-6 text-action" />Spend your TelCoins</h2>
        <p className="mt-1 text-sm text-muted">Only confirmed coins can be spent.</p>
        <div className="mt-5"><Store o={o} onBought={() => { void overview.reload(); void history.reload(); coinsChanged(); }} /></div>
      </section>

      <Contributions />

      <section className="mt-14">
        <h2 className="font-display text-2xl font-bold">History</h2>
        {history.items.length === 0 && !history.loading ? (
          <p className="mt-3 text-sm text-muted">Nothing yet. Review a product you own to earn your first coins.</p>
        ) : (
          <ul className="mt-4 divide-y divide-line overflow-hidden rounded-3xl border border-line bg-white">
            {history.items.map((e, i) => (
              <motion.li key={e.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: Math.min(i, 8) * 0.03 }} className="flex items-center justify-between gap-4 px-5 py-4 text-sm">
                <div className="flex items-center gap-3">
                  <span className={`grid size-9 place-items-center rounded-full ${e.amount < 0 ? 'bg-neutral-tint text-muted' : 'bg-gold-tint text-gold-deep'}`}><Coins className="size-4" /></span>
                  <div>
                    <p className="font-medium">{RULES[e.rule_code ?? ''] ?? ENTRY[e.entry_type] ?? e.entry_type}</p>
                    <p className="text-xs text-muted">{new Date(e.created_at).toLocaleString()} · {STATUS[e.status] ?? e.status}</p>
                  </div>
                </div>
                <p className={`font-display font-bold ${e.amount < 0 ? 'text-muted' : 'text-gold-deep'}`}>{e.amount < 0 ? '−' : '+'}{Math.abs(e.amount)}</p>
              </motion.li>
            ))}
          </ul>
        )}
        <Pager hasMore={history.hasMore} loading={history.loadingMore} onMore={history.more} shown={history.items.length} />
      </section>
    </>
  );
}

export function Rewards() {
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Telcron Rewards" title="Your TelCoins" icon={Coins}>
        Earn coins when your contributions help others. Level up, collect badges and spend them on reports and perks.
      </PageTitle>
      <Gate><RewardsBody /></Gate>
    </div>
  );
}
