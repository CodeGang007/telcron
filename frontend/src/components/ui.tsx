import {
  AlertTriangle,
  BadgeCheck,
  Bath,
  Cable,
  ChefHat,
  CircleHelp,
  Cpu,
  Loader2,
  Package,
  Refrigerator,
  ShieldX,
  Smartphone,
  Snowflake,
  Sparkles,
  Utensils,
  type LucideIcon,
} from 'lucide-react';
import { animate, motion, useInView, useMotionValue, useTransform } from 'motion/react';
import { useEffect, useRef, type ReactNode } from 'react';

const BADGES: Record<string, { label: string; cls: string; icon: LucideIcon }> = {
  verified: { label: 'Verified', cls: 'bg-ok-tint text-ok ring-ok/20', icon: BadgeCheck },
  recalled: { label: 'Recalled', cls: 'bg-danger-tint text-danger ring-danger/20', icon: ShieldX },
  certification_issue: { label: 'Certificate issue', cls: 'bg-warn-tint text-warn ring-warn/20', icon: AlertTriangle },
  needs_information: { label: 'Needs information', cls: 'bg-neutral-tint text-muted ring-ink/10', icon: CircleHelp },
};

export function StatusBadge({ badge, size = 'sm' }: { badge: string | null; size?: 'sm' | 'lg' }) {
  const b = BADGES[badge ?? ''] ?? { label: 'Not screened', cls: 'bg-neutral-tint text-muted ring-ink/10', icon: CircleHelp };
  const Icon = b.icon;
  return (
    <span className={`chip ring-1 ring-inset ${b.cls} ${size === 'lg' ? '!px-4 !py-1.5 !text-sm' : ''}`}>
      <Icon className={size === 'lg' ? 'size-4' : 'size-3.5'} strokeWidth={2.4} />
      {b.label}
    </span>
  );
}

/** The colour a trust score is shown in, by band. */
export function scoreTone(score: number | null): string {
  if (score === null) return 'var(--color-muted)';
  if (score >= 80) return 'var(--color-ok)';
  if (score >= 50) return 'var(--color-gold)';
  return 'var(--color-danger)';
}

export function AnimatedNumber({ value, className = '', decimals = 0 }: { value: number; className?: string; decimals?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => v.toLocaleString(undefined, { maximumFractionDigits: decimals, minimumFractionDigits: decimals }));
  useEffect(() => {
    if (!inView) return;
    const controls = animate(mv, value, { duration: 1.1, ease: [0.16, 1, 0.3, 1] });
    return () => controls.stop();
  }, [inView, value, mv]);
  return <motion.span ref={ref} className={className}>{text}</motion.span>;
}

/** A ring that fills to the trust score. */
export function TrustRing({ score, size = 148, label = 'Trust score' }: { score: number | null; size?: number; label?: string }) {
  const stroke = 11;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = score === null ? 0 : Math.max(0, Math.min(100, score)) / 100;
  const tone = scoreTone(score);
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }} role="img" aria-label={`${label}: ${score === null ? 'not available' : Math.round(score)} out of 100`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-line)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={tone}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          whileInView={{ strokeDashoffset: c * (1 - pct) }}
          viewport={{ once: true }}
          transition={{ duration: 1.3, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="font-display text-4xl font-extrabold tracking-tight" style={{ color: tone }}>
            {score === null ? '—' : <AnimatedNumber value={Math.round(score)} />}
          </div>
          <div className="text-[11px] font-medium uppercase tracking-wider text-muted">{label}</div>
        </div>
      </div>
    </div>
  );
}

const CATEGORY: Record<string, { icon: LucideIcon; tone: string }> = {
  Blenders: { icon: ChefHat, tone: 'from-cat-kitchen-from to-cat-kitchen-to' },
  'Mini-fridges': { icon: Refrigerator, tone: 'from-cat-cooling-from to-cat-cooling-to' },
  'Window air conditioners': { icon: Snowflake, tone: 'from-cat-air-from to-cat-air-to' },
  'Power adapters': { icon: Cable, tone: 'from-cat-power-from to-cat-power-to' },
  Smartphones: { icon: Smartphone, tone: 'from-cat-phone-from to-cat-phone-to' },
  Electronics: { icon: Cpu, tone: 'from-cat-electronics-from to-cat-electronics-to' },
  Appliances: { icon: Utensils, tone: 'from-cat-appliance-from to-cat-appliance-to' },
  'Household products': { icon: Bath, tone: 'from-cat-household-from to-cat-household-to' },
  'Food items': { icon: Sparkles, tone: 'from-cat-food-from to-cat-food-to' },
};

/** A product's picture stand-in: a tile with its category's icon. */
export function CategoryTile({ category, size = 'md' }: { category: string; size?: 'sm' | 'md' | 'lg' }) {
  const c = CATEGORY[category] ?? { icon: Package, tone: 'from-cat-other-from to-cat-other-to' };
  const Icon = c.icon;
  const box = { sm: 'size-10 rounded-xl', md: 'size-14 rounded-2xl', lg: 'size-24 rounded-3xl' }[size];
  const ic = { sm: 'size-5', md: 'size-7', lg: 'size-11' }[size];
  return (
    <span className={`grid shrink-0 place-items-center bg-gradient-to-br text-white shadow-lg ${c.tone} ${box}`}>
      <Icon className={ic} strokeWidth={1.8} />
    </span>
  );
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'error' | 'ok'; children: ReactNode }) {
  const cls = {
    info: 'bg-panel text-muted ring-ink/5',
    error: 'bg-danger-tint text-danger ring-danger/15',
    ok: 'bg-ok-tint text-ok ring-ok/15',
  }[tone];
  return (
    <motion.p
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      role={tone === 'error' ? 'alert' : 'status'}
      className={`rounded-2xl px-4 py-3 text-sm ring-1 ring-inset ${cls}`}
    >
      {children}
    </motion.p>
  );
}

export function Stars({ rating }: { rating: number }) {
  return (
    <span role="img" aria-label={`${rating} out of 5`} className="tracking-tight text-gold">
      <span aria-hidden>{'★'.repeat(rating)}</span>
      <span aria-hidden className="text-line">{'★'.repeat(5 - rating)}</span>
    </span>
  );
}

export function PageTitle({ eyebrow, title, icon: Icon, children, action }: { eyebrow?: string; title: string; icon?: LucideIcon; children?: ReactNode; action?: ReactNode }) {
  return (
    <motion.header initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }} className="mb-10 flex flex-wrap items-end justify-between gap-6">
      <div className="flex items-start gap-4">
        {Icon && (
          <span className="hidden size-12 shrink-0 place-items-center rounded-2xl bg-brand-tint text-brand-ink ring-1 ring-brand-ink/10 sm:grid">
            <Icon className="size-6" />
          </span>
        )}
        <div>
          {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
          <h1 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">{title}</h1>
          {children && <p className="mt-3 max-w-2xl text-muted">{children}</p>}
        </div>
      </div>
      {action}
    </motion.header>
  );
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

/** A grid of placeholder cards while a list loads. */
export function CardSkeletons({ count = 6, className = 'grid gap-6 md:grid-cols-2 lg:grid-cols-3' }: { count?: number; className?: string }) {
  return (
    <div className={className} role="status" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="card space-y-4">
          <div className="flex items-center gap-3">
            <Skeleton className="size-14 rounded-2xl" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-1/3" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          </div>
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-2/3" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action }: { icon: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="grid place-items-center rounded-3xl border border-dashed border-line bg-panel/60 px-6 py-16 text-center">
      <span className="relative grid size-16 place-items-center rounded-2xl bg-white text-brand-ink shadow-soft">
        <span className="absolute inset-0 rounded-2xl bg-brand-ink/10 animate-pulse-ring" />
        <Icon className="size-7" />
      </span>
      <h3 className="mt-5 font-display text-lg font-bold">{title}</h3>
      {children && <p className="mt-2 max-w-md text-sm text-muted">{children}</p>}
      {action && <div className="mt-6">{action}</div>}
    </motion.div>
  );
}

export function Spinner({ className = 'size-4' }: { className?: string }) {
  return <Loader2 className={`animate-spin ${className}`} aria-hidden />;
}

/** "Load more" under a paged list. */
export function Pager({ hasMore, loading, onMore, shown }: { hasMore: boolean; loading: boolean; onMore: () => void; shown: number }) {
  if (!hasMore && shown === 0) return null;
  return (
    <div className="mt-10 flex flex-col items-center gap-2">
      {hasMore ? (
        <button className="btn-ghost" onClick={onMore} disabled={loading}>
          {loading ? <Spinner /> : null}
          {loading ? 'Loading…' : 'Load more'}
        </button>
      ) : (
        <p className="text-xs text-muted">That is everything · {shown} shown</p>
      )}
    </div>
  );
}

/** Children that rise into view one after another. */
export const stagger = {
  container: { hidden: {}, show: { transition: { staggerChildren: 0.06 } } },
  item: { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] } } },
} as const;
