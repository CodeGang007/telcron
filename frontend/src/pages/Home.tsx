import {
  ArrowRight,
  BadgeCheck,
  Coins,
  FileSearch,
  Megaphone,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Trophy,
  Users,
  Wallet,
} from 'lucide-react';
import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { ProductCard } from '../components/ProductCard';
import { SearchBox } from '../components/SearchBox';
import { AnimatedNumber, CardSkeletons, StatusBadge, TrustRing, stagger } from '../components/ui';
import { api, type ProductSummary } from '../lib/api';
import { useLoad } from '../lib/useLoad';

type Stats = { products: number; recalls: number; passports: number; members: number; reviews: number };
type RecallLite = { id: string; title: string; recall_date: string | null; hazard: string | null; image: string | null; url: string | null };

const STEPS = [
  { icon: ScanLine, title: 'Scan or search', body: 'Point your camera at a barcode, or search by name. No account needed.' },
  { icon: FileSearch, title: 'Read the passport', body: 'Recalls, certificates and seven hazard scores, each linked to its evidence.' },
  { icon: Wallet, title: 'Save what you own', body: 'Your Digital Wallet watches every product and alerts you when something changes.' },
  { icon: Coins, title: 'Contribute and earn', body: 'Verified reviews and confirmed hazard reports earn TelCoins, levels and badges.' },
];

function PassportPreview() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30, rotate: -2 }}
      animate={{ opacity: 1, y: 0, rotate: -2 }}
      transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="relative hidden lg:block"
    >
      <div className="animate-float">
        <div className="w-[360px] rounded-[2rem] border border-white/15 bg-white p-6 text-ink shadow-[0_40px_80px_-20px_rgb(0_0_0/0.6)]">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Product passport · v3</p>
            <StatusBadge badge="verified" />
          </div>
          <p className="mt-3 font-display text-lg font-bold leading-snug">Northwind ChillMate Mini Fridge</p>
          <div className="mt-5 flex items-center gap-5">
            <TrustRing score={92} size={112} />
            <ul className="space-y-2 text-sm">
              <li className="flex items-center gap-2"><BadgeCheck className="size-4 text-ok" />No recalls found</li>
              <li className="flex items-center gap-2"><ShieldCheck className="size-4 text-ok" />ENERGY STAR valid</li>
              <li className="flex items-center gap-2"><Sparkles className="size-4 text-gold" />Low hazard</li>
            </ul>
          </div>
          <div className="mt-5 space-y-2.5">
            {[['Regulatory', 6], ['Health & safety', 18], ['Customer issues', 31]].map(([name, v], i) => (
              <div key={name}>
                <div className="flex justify-between text-xs text-muted"><span>{name}</span><span>{v}</span></div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-neutral-tint">
                  <motion.div className="h-full rounded-full bg-ok" initial={{ width: 0 }} animate={{ width: `${v}%` }} transition={{ delay: 0.9 + i * 0.15, duration: 0.9 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <motion.div
        initial={{ opacity: 0, x: 30 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 1.1 }}
        className="absolute -right-16 -top-16 rounded-2xl border border-white/10 bg-night/85 px-4 py-3 text-white shadow-2xl backdrop-blur-xl"
      >
        <p className="flex items-center gap-2 text-sm font-semibold"><Coins className="size-4 text-gold" />+25 TelCoins</p>
        <p className="text-xs text-white/60">Hazard report confirmed</p>
      </motion.div>
      <motion.div
        initial={{ opacity: 0, x: -30 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 1.4 }}
        className="absolute -bottom-8 -left-16 rounded-2xl border border-white/10 bg-night/85 px-4 py-3 text-white shadow-2xl backdrop-blur-xl"
      >
        <p className="flex items-center gap-2 text-sm font-semibold"><Megaphone className="size-4 text-rose-300" />Recall alert sent</p>
        <p className="text-xs text-white/60">to everyone who owns it</p>
      </motion.div>
    </motion.div>
  );
}

export function Home() {
  const stats = useLoad(() => api<Stats>('/stats'), []);
  const recent = useLoad(() => api<ProductSummary[]>('/products?limit=6'), []);
  const recalls = useLoad(() => api<RecallLite[]>('/recalls?limit=4'), []);

  return (
    <>
      <section className="relative overflow-hidden bg-night text-white">
        <div className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]" />
        <motion.div
          className="absolute -left-40 -top-40 size-[640px] rounded-full bg-brand-ink/40 blur-[120px]"
          animate={{ x: [0, 60, 0], y: [0, 40, 0] }}
          transition={{ duration: 16, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute -bottom-40 right-0 size-[520px] rounded-full bg-action/40 blur-[120px]"
          animate={{ x: [0, -50, 0], y: [0, -30, 0] }}
          transition={{ duration: 18, repeat: Infinity, ease: 'easeInOut' }}
        />
        <div className="container-page relative grid items-center gap-16 pb-28 pt-36 lg:grid-cols-[1.15fr_1fr] lg:pt-40">
          <motion.div variants={stagger.container} initial="hidden" animate="show">
            <motion.p variants={stagger.item} className="glass inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium text-white/80">
              <span className="size-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px] shadow-emerald-400" />
              Live recall data from the US Consumer Product Safety Commission
            </motion.p>
            <motion.h1 variants={stagger.item} className="mt-6 font-display text-5xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl">
              Know what&apos;s safe <span className="text-gradient">before you buy.</span>
            </motion.h1>
            <motion.p variants={stagger.item} className="mt-6 max-w-xl text-lg leading-relaxed text-white/70">
              Telcron gives every product one permanent record, every contributor a verified identity, and every safety claim a piece of evidence.
            </motion.p>
            <motion.div variants={stagger.item} className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
              <SearchBox dark />
            </motion.div>
            <motion.div variants={stagger.item} className="mt-4 flex flex-wrap items-center gap-3">
              <Link to="/scan" className="btn-brand"><ScanLine className="size-4" />Scan a barcode</Link>
              <Link to="/recalls" className="inline-flex items-center gap-1.5 text-sm font-medium text-white/70 hover:text-white">Latest recalls <ArrowRight className="size-4" /></Link>
            </motion.div>
          </motion.div>
          <div className="flex justify-center"><PassportPreview /></div>
        </div>
      </section>

      <section className="container-page relative z-10 -mt-12">
        <motion.dl
          variants={stagger.container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          className="grid grid-cols-2 gap-px overflow-hidden rounded-3xl border border-line bg-line shadow-lift md:grid-cols-4"
        >
          {[
            { k: 'products', label: 'Products in the registry', icon: FileSearch },
            { k: 'recalls', label: 'Recall notices tracked', icon: Megaphone },
            { k: 'passports', label: 'Passports issued', icon: ShieldCheck },
            { k: 'members', label: 'Verified members', icon: Users },
          ].map((s) => (
            <motion.div key={s.k} variants={stagger.item} className="bg-white p-6">
              <dt className="flex items-center gap-2 text-xs font-medium text-muted"><s.icon className="size-4 text-brand-ink" />{s.label}</dt>
              <dd className="mt-2 font-display text-3xl font-extrabold tracking-tight">
                {stats.data ? <AnimatedNumber value={stats.data[s.k as keyof Stats]} /> : <span className="skeleton inline-block h-8 w-20" />}
              </dd>
            </motion.div>
          ))}
        </motion.dl>
      </section>

      <section className="container-page py-24">
        <div className="mx-auto max-w-2xl text-center">
          <p className="eyebrow">How it works</p>
          <h2 className="mt-3 font-display text-4xl font-extrabold tracking-tight">From barcode to verdict in seconds</h2>
        </div>
        <motion.ol variants={stagger.container} initial="hidden" whileInView="show" viewport={{ once: true, margin: '-80px' }} className="mt-14 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <motion.li key={s.title} variants={stagger.item} className="card card-hover relative overflow-hidden">
              <span className="absolute -right-3 -top-6 font-display text-8xl font-extrabold text-panel">{i + 1}</span>
              <span className="relative grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-brand-bright to-brand-deep text-white shadow-lg">
                <s.icon className="size-6" />
              </span>
              <h3 className="relative mt-5 font-display text-lg font-bold">{s.title}</h3>
              <p className="relative mt-2 text-sm text-muted">{s.body}</p>
            </motion.li>
          ))}
        </motion.ol>
      </section>

      {recalls.data && recalls.data.length > 0 && (
        <section className="bg-panel/70 py-24">
          <div className="container-page">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="eyebrow">Just announced</p>
                <h2 className="mt-3 font-display text-4xl font-extrabold tracking-tight">Latest recall notices</h2>
              </div>
              <Link to="/recalls" className="btn-ghost">All recalls <ArrowRight className="size-4" /></Link>
            </div>
            <motion.ul variants={stagger.container} initial="hidden" whileInView="show" viewport={{ once: true }} className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              {recalls.data.map((r) => (
                <motion.li key={r.id} variants={stagger.item} className="card card-hover flex flex-col overflow-hidden !p-0">
                  <div className="relative h-40 bg-white">
                    {r.image ? (
                      <img src={r.image} alt="" loading="lazy" className="h-full w-full object-contain p-4" />
                    ) : (
                      <div className="grid h-full place-items-center bg-danger-tint text-danger"><Megaphone className="size-10" /></div>
                    )}
                    <span className="chip absolute left-3 top-3 bg-danger text-white">Recall</span>
                  </div>
                  <div className="flex flex-1 flex-col p-5">
                    <p className="text-xs text-muted">{r.recall_date ? new Date(r.recall_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : ''}</p>
                    <p className="mt-1 line-clamp-3 text-sm font-semibold">{r.title}</p>
                    {r.url && <a href={r.url} target="_blank" rel="noreferrer noopener" className="mt-auto pt-3 text-xs font-semibold text-action">Official notice →</a>}
                  </div>
                </motion.li>
              ))}
            </motion.ul>
          </div>
        </section>
      )}

      <section className="container-page py-24">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Fresh passports</p>
            <h2 className="mt-3 font-display text-4xl font-extrabold tracking-tight">Recently screened</h2>
          </div>
          <Link to="/search" className="btn-ghost">Browse all <ArrowRight className="size-4" /></Link>
        </div>
        <div className="mt-10">
          {recent.loading ? (
            <CardSkeletons count={3} />
          ) : (
            <motion.div variants={stagger.container} initial="hidden" whileInView="show" viewport={{ once: true }} className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {recent.data?.map((p) => <ProductCard key={p.id} product={p} />)}
            </motion.div>
          )}
        </div>
      </section>

      <section className="container-page pb-24">
        <div className="relative overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-brand-deep via-brand to-brand-ink px-8 py-16 text-white sm:px-16">
          <div className="bg-grid absolute inset-0 opacity-60" />
          <div className="relative grid items-center gap-8 lg:grid-cols-[1.4fr_1fr]">
            <div>
              <h2 className="font-display text-4xl font-extrabold tracking-tight">Own something? Make it safer for everyone.</h2>
              <p className="mt-4 max-w-xl text-white/75">Create your TelcronID, save your products, and earn TelCoins when your reviews and hazard reports help others.</p>
            </div>
            <div className="flex flex-wrap gap-3 lg:justify-end">
              <Link to="/sign-up" className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-brand transition hover:-translate-y-0.5">Create your TelcronID <ArrowRight className="size-4" /></Link>
              <Link to="/leaderboard" className="glass inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-semibold text-white"><Trophy className="size-4" />Leaderboard</Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
