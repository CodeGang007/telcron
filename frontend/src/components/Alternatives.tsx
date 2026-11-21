import { ExternalLink, Loader2, ScanSearch, ShieldCheck, ShoppingBag, Star } from 'lucide-react';
import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../lib/auth';
import { track } from '../lib/researching';
import { api, apiUrl, explain, post, type ProductSummary } from '../lib/api';
import { CategoryTile, Skeleton, scoreTone } from './ui';

type Alt = ProductSummary & { closeness: number | null; rating: number | null; reviews: number };
type Alternatives = { basis: 'meaning' | 'category'; trust_floor: number; items: Alt[] };

type Store = { name: string; url: (q: string) => string };
const S = (name: string, url: (q: string) => string): Store => ({ name, url });
const GOOGLE = S('Google Shopping', (q) => `https://www.google.com/search?tbm=shop&q=${q}`);
/** Plain search links (no affiliate tags) to the big stores in each country, most used first. */
const STORES: Record<string, Store[]> = {
  IN: [S('Amazon', (q) => `https://www.amazon.in/s?k=${q}`), S('Flipkart', (q) => `https://www.flipkart.com/search?q=${q}`),
    S('Croma', (q) => `https://www.croma.com/searchB?q=${q}`), S('Reliance Digital', (q) => `https://www.reliancedigital.in/search?q=${q}`), GOOGLE],
  US: [S('Amazon', (q) => `https://www.amazon.com/s?k=${q}`), S('Walmart', (q) => `https://www.walmart.com/search?q=${q}`),
    S('Best Buy', (q) => `https://www.bestbuy.com/site/searchpage.jsp?st=${q}`), S('Target', (q) => `https://www.target.com/s?searchTerm=${q}`),
    S('eBay', (q) => `https://www.ebay.com/sch/i.html?_nkw=${q}`), GOOGLE],
  GB: [S('Amazon', (q) => `https://www.amazon.co.uk/s?k=${q}`), S('Argos', (q) => `https://www.argos.co.uk/search/${q}/`),
    S('Currys', (q) => `https://www.currys.co.uk/search?q=${q}`), S('eBay', (q) => `https://www.ebay.co.uk/sch/i.html?_nkw=${q}`), GOOGLE],
  CA: [S('Amazon', (q) => `https://www.amazon.ca/s?k=${q}`), S('Walmart', (q) => `https://www.walmart.ca/search?q=${q}`),
    S('Best Buy', (q) => `https://www.bestbuy.ca/en-ca/search?search=${q}`), S('eBay', (q) => `https://www.ebay.ca/sch/i.html?_nkw=${q}`), GOOGLE],
  AU: [S('Amazon', (q) => `https://www.amazon.com.au/s?k=${q}`), S('JB Hi-Fi', (q) => `https://www.jbhifi.com.au/search?query=${q}`),
    S('eBay', (q) => `https://www.ebay.com.au/sch/i.html?_nkw=${q}`), GOOGLE],
  AE: [S('Amazon', (q) => `https://www.amazon.ae/s?k=${q}`), S('Noon', (q) => `https://www.noon.com/uae-en/search/?q=${q}`), GOOGLE],
  DE: [S('Amazon', (q) => `https://www.amazon.de/s?k=${q}`), S('eBay', (q) => `https://www.ebay.de/sch/i.html?_nkw=${q}`), GOOGLE],
};

function region() {
  const tag = (navigator.languages?.[0] ?? navigator.language ?? 'en-US').split('-')[1]?.toUpperCase();
  return tag && STORES[tag] ? tag : 'US';
}

/** Where to buy it: searches in the shopper's own country's stores. */
export function storesFor(p: { name: string; brand: string | null; model_number: string | null }) {
  const q = encodeURIComponent([p.brand && !p.name.toLowerCase().startsWith(p.brand.toLowerCase()) ? p.brand : '', p.name, p.model_number ?? '']
    .join(' ').replace(/\s+/g, ' ').trim());
  return (STORES[region()] ?? STORES.US!).map((s) => ({ name: s.name, url: s.url(q) }));
}

/** A row of store links: the first two as buttons, the rest behind "More stores". */
export function StoreLinks({ product, compact = false }: { product: { name: string; brand: string | null; model_number: string | null }; compact?: boolean }) {
  const [more, setMore] = useState(false);
  const stores = storesFor(product);
  const shown = compact && !more ? stores.slice(0, 2) : stores;
  return (
    <div className="flex flex-wrap gap-2">
      {shown.map((s, i) => (
        <a key={s.name} href={s.url} target="_blank" rel="noreferrer noopener"
          className={`btn-ghost btn-sm ${compact ? 'flex-1 justify-center' : ''}`}>
          {i === 0 && <ShoppingBag className="size-3.5" />}{s.name}<ExternalLink className="size-3" />
        </a>
      ))}
      {compact && !more && stores.length > 2 && (
        <button type="button" onClick={() => setMore(true)} className="btn-ghost btn-sm">+{stores.length - 2} more</button>
      )}
    </div>
  );
}

type Listing = { title: string; url: string; store: string; price: string | null; rating: number | null; same_brand: boolean };

/** Real listings of products like this one on the marketplaces in the shopper's country. Not checked
    by Telcron: a member can ask for one to be added and researched. */
function Marketplace({ slug }: { slug: string }) {
  const { me } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState<Listing[] | null>(null);
  const [checking, setChecking] = useState<string | null>(null);
  useEffect(() => {
    api<{ available: boolean; items: Listing[] }>(`/products/${slug}/marketplace?country=${region()}`)
      .then((r) => setItems(r.items)).catch(() => setItems([]));
  }, [slug]);
  const check = async (l: Listing) => {
    setChecking(l.url);
    try {
      const r = await post<{ slug: string; new: boolean }>(`/products/${slug}/marketplace/check`, { title: l.title, url: l.url });
      track(r.slug, l.title.slice(0, 60));
      toast.success(r.new ? 'Added: researching it now' : 'Already in Telcron', { action: { label: 'Open', onClick: () => navigate(`/products/${r.slug}`) } });
    } catch (e) {
      toast.error(explain(e));
    } finally {
      setChecking(null);
    }
  };
  if (items === null) return <div className="mt-6 grid gap-3 sm:grid-cols-2">{[0, 1].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}</div>;
  if (items.length === 0) return null;
  return (
    <div className="mt-8">
      <h3 className="flex items-center gap-2 font-display text-lg font-bold"><ShoppingBag className="size-5 text-action" />Popular on marketplaces</h3>
      <p className="mt-1 text-sm text-muted">Real listings of similar products in your country's shops. <span className="font-semibold text-ink">Not checked by Telcron yet</span>: use “Check it” and we research its safety and reviews.</p>
      <ul className="mt-4 grid gap-3 sm:grid-cols-2">
        {items.map((l, i) => (
          <motion.li key={l.url} initial={{ opacity: 0, y: 6 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.04 }}
            className="flex flex-col rounded-2xl border border-line p-4">
            <a href={l.url} target="_blank" rel="noreferrer noopener" className="line-clamp-2 text-sm font-semibold hover:text-action">{l.title}</a>
            <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
              <span className="chip bg-panel text-muted !py-0">{l.store}</span>
              {l.price && <span className="font-semibold text-ink">{l.price}</span>}
              {l.rating !== null && <span className="inline-flex items-center gap-1"><Star className="size-3.5 fill-gold text-gold" />{l.rating}</span>}
              {l.same_brand && <span>same brand</span>}
            </p>
            <div className="mt-auto flex gap-2 pt-3">
              <a href={l.url} target="_blank" rel="noreferrer noopener" className="btn-ghost btn-sm flex-1 justify-center">View listing<ExternalLink className="size-3" /></a>
              {me && me.verification_level >= 1 && (
                <button className="btn btn-sm flex-1 justify-center" disabled={checking === l.url} onClick={() => void check(l)}>
                  {checking === l.url ? <Loader2 className="size-3.5 animate-spin" /> : <ScanSearch className="size-3.5" />}Check it
                </button>
              )}
            </div>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

/** Similar products Telcron has verified as at least as safe, with where to find them. */
export function Alternatives({ slug, category }: { slug: string; category: string }) {
  const [data, setData] = useState<Alternatives | null>(null);
  useEffect(() => {
    api<Alternatives>(`/products/${slug}/alternatives`).then(setData).catch(() => setData({ basis: 'category', trust_floor: 60, items: [] }));
  }, [slug]);

  return (
    <section aria-labelledby="alternatives" className="card">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="alternatives" className="flex items-center gap-2 font-display text-xl font-bold"><ShieldCheck className="size-5 text-ok" />Safer alternatives</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Similar products with a verified passport and a trust score of at least {Math.round(data?.trust_floor ?? 60)}, ranked by safety, then by what owners say.
            Store links are plain searches in your country's shops; Telcron sells nothing and earns nothing from them.
          </p>
        </div>
      </div>
      {!data ? (
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-40 rounded-3xl" />)}</div>
      ) : data.items.length === 0 ? (
        <p className="mt-5 rounded-2xl bg-panel px-4 py-3 text-sm text-muted">No verified alternatives in {category.toLowerCase()} yet. Telcron lists only products it has checked here; similar products on marketplaces are below.</p>
      ) : (
        <ul className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((p, i) => {
            return (
              <motion.li key={p.id} initial={{ opacity: 0, y: 8 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }}
                className="flex flex-col rounded-3xl border border-line p-4 transition hover:border-ok hover:shadow-soft">
                <Link to={`/products/${p.slug}`} className="group flex items-start gap-3">
                  {p.image_url ? <img src={apiUrl(p.image_url)} alt="" className="size-12 shrink-0 rounded-2xl border border-line object-cover" /> : <CategoryTile category={p.category} />}
                  <div className="min-w-0">
                    <p className="line-clamp-2 font-semibold leading-snug group-hover:text-brand-ink">{p.name}</p>
                    <p className="mt-0.5 truncate text-xs text-muted">{[p.brand, p.model_number].filter(Boolean).join(' · ')}</p>
                  </div>
                </Link>
                <div className="mt-3 flex items-center gap-2 text-xs">
                  <span className="chip bg-ok-tint text-ok"><ShieldCheck className="size-3.5" />Verified</span>
                  {p.trust_score !== null && <span className="font-semibold" style={{ color: scoreTone(p.trust_score) }}>Trust {Math.round(p.trust_score)}</span>}
                  <span className="inline-flex items-center gap-1 text-muted">
                    · <Star className={`size-3.5 ${p.rating ? 'fill-gold text-gold' : ''}`} />{p.rating ? `${p.rating} (${p.reviews})` : 'no reviews yet'}
                  </span>
                </div>
                <div className="mt-auto pt-4"><StoreLinks product={p} compact /></div>
              </motion.li>
            );
          })}
        </ul>
      )}
      <Marketplace slug={slug} />
    </section>
  );
}
