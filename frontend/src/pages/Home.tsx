import { Link } from 'react-router-dom';
import { ProductCard } from '../components/ProductCard';
import { SearchBox } from '../components/SearchBox';
import { api, type ProductSummary } from '../lib/api';
import { useLoad } from '../lib/useLoad';

const STEPS = [
  { title: 'Scan or search', body: 'Find a product by name, brand or barcode. No account needed.' },
  { title: 'Read its passport', body: 'Recalls, certificates and seven hazard scores, each with its evidence.' },
  { title: 'Contribute and earn', body: 'Verified reviews and hazard flags earn TelCoins when they prove useful.' },
];

export function Home() {
  const recent = useLoad(() => api<ProductSummary[]>('/products?limit=3'), []);
  return (
    <>
      <section className="bg-brand text-white">
        <div className="container-page py-20 sm:py-28">
          <h1 className="max-w-2xl text-5xl font-medium leading-tight sm:text-7xl">
            A smarter way to product safety
          </h1>
          <p className="mt-8 max-w-2xl text-lg leading-relaxed">
            Telcron gives every product one permanent record, every contributor a verified
            identity, and every safety claim a piece of evidence.
          </p>
          <div className="mt-10">
            <SearchBox />
          </div>
        </div>
      </section>

      <section className="container-page -mt-8 grid gap-6 sm:grid-cols-2">
        {[
          { to: '/search', title: 'Check a product', sub: 'Recalls, certificates and hazard scores' },
          { to: '/wallet', title: 'Open your Digital Wallet', sub: 'Get alerted when a passport changes' },
        ].map((c) => (
          <Link
            key={c.to}
            to={c.to}
            className="rounded-3xl border border-line bg-brand-tint p-8 text-center transition hover:border-brand-ink"
          >
            <p className="font-semibold text-brand-ink">{c.title}</p>
            <p className="mt-1 text-sm text-muted">{c.sub}</p>
          </Link>
        ))}
      </section>

      <section className="container-page py-16">
        <div className="rounded-3xl bg-panel px-6 py-12 sm:px-12">
          <h2 className="text-center text-3xl font-semibold">How Telcron works</h2>
          <ol className="mt-10 grid gap-8 sm:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="text-center">
                <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-white font-semibold text-brand-ink">
                  {i + 1}
                </span>
                <h3 className="mt-4 font-semibold text-brand-ink">{s.title}</h3>
                <p className="mt-2 text-sm text-muted">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {recent.data && recent.data.length > 0 && (
        <section className="container-page pb-20">
          <div className="rounded-3xl bg-warm px-6 py-12 sm:px-12">
            <h2 className="text-center text-3xl font-semibold">Recently screened</h2>
            <div className="mt-10 grid gap-6 md:grid-cols-3">
              {recent.data.map((p) => (
                <ProductCard key={p.id} product={p} />
              ))}
            </div>
          </div>
        </section>
      )}
    </>
  );
}
