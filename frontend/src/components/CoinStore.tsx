import confetti from 'canvas-confetti';
import { Coins, FileText, Flame, Lock, ShieldAlert, ShoppingBag, Sparkles, type LucideIcon } from 'lucide-react';
import { motion } from 'motion/react';
import { useState } from 'react';
import { toast } from 'sonner';
import { api, explain, post } from '../lib/api';
import { tokenHex } from '../lib/tokens';
import { useLoad } from '../lib/useLoad';
import { stagger } from './ui';

export type StoreItem = { code: string; name: string; cost: number; kind: string; needs_product: boolean };
type Choice = { slug: string; name: string };

const STORE_ICON: Record<string, LucideIcon> = { pdf_report: FileText, watchlist_slots: ShieldAlert, feature_access: Sparkles, rate_limit_boost: Flame, data_export: FileText, invoice_discount: Coins };

/** The coin store. A product item can be bought for the product the member came from
    (`/rewards?product=<slug>`, DEF-119) as well as any product in their wallet: `POST /redemptions`
    accepts any product (CT-002). */
export function CoinStore({ items, confirmed, product, onBought }: { items: StoreItem[]; confirmed: number; product: string | null; onBought: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const owned = useLoad(() => api<Choice[]>('/wallet/items'), []);
  // The product the member came from, by name, when it is not already in their wallet.
  const asked = useLoad(() => (product ? api<Choice>(`/products/${product}`).then((p) => ({ slug: p.slug, name: p.name })) : Promise.resolve(null)), [product]);
  const choices: Choice[] = [
    ...(asked.data && !owned.data?.some((w) => w.slug === asked.data!.slug) ? [asked.data] : []),
    ...(owned.data ?? []),
  ];
  const [chosen, setChosen] = useState<string>('');
  const selected = chosen || asked.data?.slug || choices[0]?.slug || '';

  const buy = async (item: StoreItem) => {
    const slug = item.needs_product ? selected : undefined;
    if (item.needs_product && !slug) return;
    setBusy(item.code);
    try {
      const r = await post<{ report: string | null }>('/redemptions', { item_code: item.code, product: slug ?? null, request_id: crypto.randomUUID() });
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

  const loadingChoices = owned.loading || asked.loading;
  return (
    <>
      {product && asked.error && !asked.loading && (
        <p role="alert" className="mb-4 text-sm text-warn">We could not find the product you came from. Pick one from your wallet, or open the product again and use its report link.</p>
      )}
      <motion.ul variants={stagger.container} initial="hidden" whileInView="show" viewport={{ once: true }} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => {
          const Icon = STORE_ICON[item.kind] ?? ShoppingBag;
          const affordable = confirmed >= item.cost;
          return (
            <motion.li key={item.code} variants={stagger.item} className={`card card-hover flex flex-col ${item.needs_product && asked.data ? 'ring-2 ring-action/40' : ''}`}>
              <span className="grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-violet to-action text-white shadow-lg"><Icon className="size-6" /></span>
              <p className="mt-4 font-semibold">{item.name}</p>
              {item.needs_product && (
                choices.length > 0 ? (
                  <label className="mt-3 block text-xs text-muted">
                    For
                    <select className="field mt-1 !py-2 text-sm" value={selected} onChange={(e) => setChosen(e.target.value)}>
                      {choices.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
                    </select>
                  </label>
                ) : (
                  <p className="mt-3 text-xs text-muted">{loadingChoices ? 'Loading your products…' : 'Open a product and use “Get the full report with TelCoins”, or save one to your wallet.'}</p>
                )
              )}
              <div className="mt-auto flex items-center justify-between pt-5">
                <span className="chip bg-gold-tint text-gold-ink"><Coins className="size-3.5" />{item.cost.toLocaleString()}</span>
                <button className="btn btn-sm" disabled={!affordable || busy === item.code || (item.needs_product && !selected)} onClick={() => buy(item)}>
                  {busy === item.code ? 'Redeeming…' : affordable ? 'Redeem' : <><Lock className="size-3.5" />{(item.cost - confirmed).toLocaleString()} more</>}
                </button>
              </div>
            </motion.li>
          );
        })}
      </motion.ul>
    </>
  );
}
