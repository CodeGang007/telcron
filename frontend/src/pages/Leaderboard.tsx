import { Crown, Medal, Trophy } from 'lucide-react';
import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { EmptyState, Notice, PageTitle, Skeleton } from '../components/ui';
import { api } from '../lib/api';
import { useLoad } from '../lib/useLoad';

type Row = { rank: number; display_name: string; coins: number };
const PODIUM = [
  { place: 2, height: 'h-28', tone: 'from-silver-light to-silver', icon: Medal },
  { place: 1, height: 'h-40', tone: 'from-gold-light to-gold-deep', icon: Crown },
  { place: 3, height: 'h-20', tone: 'from-bronze-light to-bronze', icon: Medal },
];

export function Leaderboard() {
  const rows = useLoad(() => api<Row[]>('/leaderboard?limit=50'), []);
  const month = new Date().toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  const top = rows.data?.slice(0, 3) ?? [];
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Community" title={`Top contributors · ${month}`} icon={Trophy}>
        Ranked by TelCoins confirmed this month. Resets on the first of every month.
      </PageTitle>
      {rows.loading && <Skeleton className="h-72 w-full rounded-[2rem]" />}
      {rows.error && <Notice tone="error">{rows.error} <button className="font-semibold underline" onClick={() => void rows.reload()}>Try again</button></Notice>}
      {rows.data?.length === 0 && (
        <EmptyState icon={Trophy} title="No confirmed contributions yet this month" action={<Link to="/search" className="btn">Find a product to review</Link>}>
          Yours could be the first.
        </EmptyState>
      )}
      {top.length > 0 && (
        <div className="relative overflow-hidden rounded-[2rem] bg-night px-6 pb-0 pt-12 text-white">
          <div className="bg-grid absolute inset-0 opacity-60" />
          <div className="relative mx-auto grid max-w-2xl grid-cols-3 items-end gap-4">
            {PODIUM.map((slot, i) => {
              const row = top.find((r) => r.rank === slot.place);
              if (!row) return <div key={slot.place} />;
              return (
                <motion.div key={slot.place} initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 * i, type: 'spring', stiffness: 120 }} className="flex flex-col items-center">
                  <slot.icon className={`size-7 ${slot.place === 1 ? 'text-gold' : 'text-white/70'}`} />
                  <span className={`mt-2 grid size-16 place-items-center rounded-full bg-gradient-to-br text-xl font-bold shadow-xl ring-4 ring-white/10 ${slot.tone}`}>
                    {row.display_name.slice(0, 1)}
                  </span>
                  <p className="mt-2 max-w-full truncate text-sm font-semibold">{row.display_name}</p>
                  <p className="text-xs text-white/60">{row.coins.toLocaleString()} coins</p>
                  <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} transition={{ delay: 0.3 + 0.15 * i, duration: 0.6 }} className={`mt-3 w-full overflow-hidden rounded-t-2xl bg-gradient-to-b ${slot.tone} ${slot.height} grid place-items-center font-display text-4xl font-extrabold text-white/90`}>
                    {slot.place}
                  </motion.div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}
      {rows.data && rows.data.length > 3 && (
        <ol className="mt-8 divide-y divide-line overflow-hidden rounded-3xl border border-line bg-white">
          {rows.data.slice(3).map((r, i) => (
            <motion.li key={r.rank} initial={{ opacity: 0, x: -10 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.03 }} className="flex items-center justify-between px-5 py-4">
              <span className="flex items-center gap-4">
                <span className="w-6 text-center font-display font-bold text-muted">{r.rank}</span>
                <span className="grid size-9 place-items-center rounded-full bg-panel text-sm font-semibold">{r.display_name.slice(0, 1)}</span>
                {r.display_name}
              </span>
              <span className="font-display font-bold text-gold-deep">{r.coins.toLocaleString()}</span>
            </motion.li>
          ))}
        </ol>
      )}
    </div>
  );
}
