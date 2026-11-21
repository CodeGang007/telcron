import { ExternalLink, Megaphone, Search, ShieldAlert, Wrench } from 'lucide-react';
import { motion } from 'motion/react';
import { useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CardSkeletons, EmptyState, Notice, PageTitle, Pager, stagger } from '../components/ui';
import { usePaged } from '../lib/usePaged';

type Recall = {
  id: string; source: string; recall_number: string | null; title: string; hazard: string | null;
  remedy: string | null; recall_date: string | null; url: string | null; products: string[]; image: string | null;
};
const SOURCE: Record<string, string> = { cpsc: 'US Consumer Product Safety Commission', openfda: 'US Food and Drug Administration' };

export function Recalls() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const [text, setText] = useState(q);
  const recalls = usePaged<Recall>(`/recalls?q=${encodeURIComponent(q)}`, 10);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setParams(text.trim() ? { q: text.trim() } : {});
  };
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Recalls" title={q ? `Recall notices about “${q}”` : 'Latest recall notices'} icon={Megaphone}>
        Official notices, as published by the authority that issued them. A product in the registry that a notice names is re-screened automatically.
      </PageTitle>
      <form onSubmit={submit} role="search" className="flex max-w-2xl items-center gap-2 rounded-2xl border border-line bg-white p-1.5 shadow-soft focus-within:border-action focus-within:ring-4 focus-within:ring-action/10">
        <Search className="ml-3 size-5 text-muted" />
        <label className="sr-only" htmlFor="recall-search">Search recall notices</label>
        <input id="recall-search" className="min-w-0 flex-1 bg-transparent px-1 py-2.5 text-sm outline-none" placeholder="Search recall notices, for example heater or burn" value={text} onChange={(e) => setText(e.target.value)} />
        <button className="btn !rounded-xl !px-5">Search</button>
      </form>
      <div className="mt-10">
        {recalls.loading && <CardSkeletons count={4} className="space-y-4" />}
        {recalls.error && <Notice tone="error">{recalls.error}</Notice>}
        {!recalls.loading && recalls.items.length === 0 && (
          <EmptyState icon={Megaphone} title={q ? `No notice mentions “${q}”` : 'No recall notices yet'}>
            {q ? 'Try a product type or a hazard.' : 'An administrator can import them from the data sources page.'}
          </EmptyState>
        )}
        <motion.ul key={q} variants={stagger.container} initial="hidden" animate="show" className="space-y-4">
          {recalls.items.map((r) => (
            <motion.li key={r.id} variants={stagger.item} className="card card-hover grid gap-5 sm:grid-cols-[160px_1fr]">
              <div className="grid h-40 place-items-center overflow-hidden rounded-2xl border border-line bg-white sm:h-full">
                {r.image ? <img src={r.image} alt="" loading="lazy" className="max-h-40 w-full object-contain p-3" /> : <ShieldAlert className="size-12 text-danger/40" />}
              </div>
              <div>
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <p className="eyebrow">{SOURCE[r.source] ?? r.source}</p>
                  <p className="text-xs text-muted">{r.recall_date ? new Date(r.recall_date).toLocaleDateString() : ''}{r.recall_number ? ` · No. ${r.recall_number}` : ''}</p>
                </div>
                <h2 className="mt-2 font-display text-lg font-bold leading-snug">{r.title}</h2>
                {r.hazard && <p className="mt-3 flex gap-2 text-sm"><ShieldAlert className="mt-0.5 size-4 shrink-0 text-danger" /><span><span className="font-semibold text-danger">Hazard: </span>{r.hazard}</span></p>}
                {r.remedy && <p className="mt-2 flex gap-2 text-sm text-muted"><Wrench className="mt-0.5 size-4 shrink-0 text-ink" /><span><span className="font-semibold text-ink">What to do: </span>{r.remedy}</span></p>}
                {r.url && (
                  <a className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-action" href={r.url} target="_blank" rel="noreferrer noopener">
                    Read the official notice <ExternalLink className="size-3.5" />
                  </a>
                )}
              </div>
            </motion.li>
          ))}
        </motion.ul>
        <Pager hasMore={recalls.hasMore} loading={recalls.loadingMore} onMore={recalls.more} shown={recalls.items.length} />
      </div>
    </div>
  );
}
