import { useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Notice, PageTitle } from '../components/ui';
import { api } from '../lib/api';
import { useLoad } from '../lib/useLoad';

type Recall = {
  id: string;
  source: string;
  recall_number: string | null;
  title: string;
  hazard: string | null;
  remedy: string | null;
  recall_date: string | null;
  url: string | null;
  products: string[];
};
const SOURCE: Record<string, string> = { cpsc: 'US Consumer Product Safety Commission', openfda: 'US Food and Drug Administration' };

export function Recalls() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const [text, setText] = useState(q);
  const recalls = useLoad(() => api<Recall[]>(`/recalls?q=${encodeURIComponent(q)}`), [q]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setParams(text.trim() ? { q: text.trim() } : {});
  };
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Recalls" title={q ? `Recall notices about “${q}”` : 'Latest recall notices'}>
        Official notices, as published by the authority that issued them. A product in the registry that a notice names is re-screened automatically.
      </PageTitle>
      <form onSubmit={submit} role="search" className="flex max-w-2xl gap-2">
        <label className="sr-only" htmlFor="recall-search">Search recall notices</label>
        <input id="recall-search" className="field !rounded-lg" placeholder="Search recall notices, for example heater or burn" value={text} onChange={(e) => setText(e.target.value)} />
        <button className="btn shrink-0">Search</button>
      </form>
      <div className="mt-10">
        {recalls.loading && <Notice>Loading notices…</Notice>}
        {recalls.error && <Notice tone="error">{recalls.error}</Notice>}
        {recalls.data?.length === 0 && (
          <Notice>{q ? `No notice mentions “${q}”. Try a product type or a hazard.` : 'No recall notices have been imported yet.'}</Notice>
        )}
        <ul className="space-y-4">
          {recalls.data?.map((r) => (
            <li key={r.id} className="card">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <p className="eyebrow">{SOURCE[r.source] ?? r.source}</p>
                <p className="text-xs text-muted">
                  {r.recall_date ? new Date(r.recall_date).toLocaleDateString() : ''}{r.recall_number ? ` · No. ${r.recall_number}` : ''}
                </p>
              </div>
              <h2 className="mt-2 text-lg font-semibold">{r.title}</h2>
              {r.hazard && <p className="mt-2 text-sm"><span className="font-semibold text-danger">Hazard: </span>{r.hazard}</p>}
              {r.remedy && <p className="mt-2 text-sm text-muted"><span className="font-semibold text-ink">What to do: </span>{r.remedy}</p>}
              {r.url && (
                <a className="mt-3 inline-block text-sm text-action underline" href={r.url} target="_blank" rel="noreferrer noopener">Read the official notice</a>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
