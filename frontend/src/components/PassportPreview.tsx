import { AlertOctagon, BadgeCheck, Coins, Megaphone, Sparkles } from 'lucide-react';
import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { api, type Passport, type ProductSummary } from '../lib/api';
import { useLoad } from '../lib/useLoad';
import { StatusBadge, TrustRing } from './ui';

const tone = (score: number) => (score >= 60 ? 'bg-danger' : score >= 30 ? 'bg-gold' : 'bg-ok');

/** The hero's passport card, read from a real product's current passport. Every figure on it is
    the API's: a hand-written passport for a real product would disagree with the product page
    ("the passport is honest", DEF-037). With no screened product to show, nothing is drawn. */
export function PassportPreview({ products }: { products: ProductSummary[] | null }) {
  const pick = products?.find((p) => p.trust_score !== null && !p.demo) ?? products?.find((p) => p.trust_score !== null);
  const passport = useLoad(() => (pick ? api<Passport>(`/products/${pick.slug}/passport`) : Promise.resolve(null)), [pick?.slug]);
  const pass = passport.data;
  // Hold the hero's shape while loading; nothing at all if no product has a passport yet.
  if (!pick || !pass) return products === null || passport.loading ? <div className="hidden h-[26rem] w-[360px] animate-pulse rounded-[2rem] bg-white/10 lg:block" /> : null;
  const recalls = pass.recall_matches.filter((r) => r.verdict === 'match' || r.verdict === 'near_match').length;
  const scored = (pass.hazard?.dimensions ?? []).filter((d) => d.status === 'scored' && d.score !== null).slice(0, 3);
  return (
    <motion.div
      initial={{ opacity: 0, y: 30, rotate: -2 }}
      animate={{ opacity: 1, y: 0, rotate: -2 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      className="relative hidden lg:block"
    >
      <div className="animate-float">
        <Link to={`/products/${pick.slug}`} className="block w-[360px] rounded-[2rem] border border-white/15 bg-white p-6 text-ink shadow-deep transition hover:shadow-lift">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Product passport · v{pass.version}</p>
            <StatusBadge badge={pass.status_badge} />
          </div>
          <p className="mt-3 font-display text-lg font-bold leading-snug">{pick.name}</p>
          <div className="mt-5 flex items-center gap-5">
            <TrustRing score={pass.trust_score} size={112} />
            <ul className="space-y-2 text-sm">
              <li className="flex items-center gap-2">
                {recalls ? <AlertOctagon className="size-4 text-danger" /> : <BadgeCheck className="size-4 text-ok" />}
                {recalls ? `${recalls} recall notice${recalls === 1 ? '' : 's'}` : 'No recall notice names it'}
              </li>
              {pass.hazard?.label && <li className="flex items-center gap-2"><Sparkles className="size-4 text-gold" />{pass.hazard.label} hazard</li>}
            </ul>
          </div>
          {scored.length > 0 && (
            <div className="mt-5 space-y-2.5">
              {scored.map((d, i) => (
                <div key={d.code}>
                  <div className="flex justify-between text-xs text-muted"><span>{d.name}</span><span>{Math.round(d.score!)}</span></div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-neutral-tint">
                    <motion.div className={`h-full rounded-full ${tone(d.score!)}`} initial={{ width: 0 }} animate={{ width: `${Math.max(3, d.score!)}%` }} transition={{ delay: 0.6 + i * 0.15, duration: 0.9 }} />
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-4 text-xs text-muted">Live from the registry · {new Date(pass.verified_at).toLocaleDateString()}</p>
        </Link>
      </div>
      {/* What Telcron does, not figures about this product: 25 is the reward for a confirmed hazard report. */}
      <motion.div
        initial={{ opacity: 0, x: 30 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.9 }}
        className="absolute -right-16 -top-16 rounded-2xl border border-white/10 bg-night/85 px-4 py-3 text-white shadow-2xl backdrop-blur-xl"
      >
        <p className="flex items-center gap-2 text-sm font-semibold"><Coins className="size-4 text-gold" />+25 TelCoins</p>
        <p className="text-xs text-white/60">for a confirmed hazard report</p>
      </motion.div>
      <motion.div
        initial={{ opacity: 0, x: -30 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 1.2 }}
        className="absolute -bottom-8 -left-16 rounded-2xl border border-white/10 bg-night/85 px-4 py-3 text-white shadow-2xl backdrop-blur-xl"
      >
        <p className="flex items-center gap-2 text-sm font-semibold"><Megaphone className="size-4 text-brand-soft" />Recall alerts</p>
        <p className="text-xs text-white/60">to everyone who saved it</p>
      </motion.div>
    </motion.div>
  );
}
