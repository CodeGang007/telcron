import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Notice, PageTitle } from '../components/ui';
import { api, explain, post } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useLoad } from '../lib/useLoad';

type Job = {
  id: string;
  source: string;
  trigger: string;
  status: string;
  // Recall imports carry a date range; a product research run (`web_search`) carries the product.
  params: { date_start?: string; date_end?: string; product_id?: string; reread?: string };
  // `errors` is a count for recall imports and a list of "source: what went wrong" for research runs.
  stats: {
    fetched?: number; new?: number; changed?: number; unchanged?: number; errors?: number | string[]; products_rescreened?: number;
    pages?: number; findings?: number; cpsc_notices?: number;
  } | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
};
const TONE: Record<string, string> = {
  succeeded: 'bg-ok-tint text-ok', partial: 'bg-warn-tint text-warn', failed: 'bg-danger-tint text-danger',
  queued: 'bg-neutral-tint text-muted', running: 'bg-neutral-tint text-muted',
};
const active = (j: Job) => j.status === 'queued' || j.status === 'running';
const research = (j: Job) => j.source === 'web_search';

// What started a run, in words. Research runs are started per product: by the nightly sweep of new
// and due products, by a member asking on the product page, or by an admin (DEF-033).
function startedBy(j: Job) {
  if (research(j)) return { schedule: 'automatic (new or due product)', event: 'a member asked', admin: 'an admin asked' }[j.trigger] ?? j.trigger;
  return { schedule: 'nightly', admin: 'by hand', event: 'by hand' }[j.trigger] ?? j.trigger;
}

const SOURCE_NAME: Record<string, string> = {
  cpsc: 'CPSC recall notices', web: 'Web search', reader: 'Reading the pages found', uk_opss: 'UK product safety notices',
};
/** "web: no search provider configured" -> "Web search: no search provider configured." */
function sentence(raw: string) {
  const [head = '', ...rest] = raw.split(':');
  const text = rest.join(':').trim();
  const out = text ? `${SOURCE_NAME[head.trim()] ?? head.trim()}: ${text}` : raw.trim();
  return /[.!?]$/.test(out) ? out : `${out}.`;
}

function Summary({ j }: { j: Job }) {
  const s = j.stats ?? {};
  if (research(j)) {
    const errors = Array.isArray(s.errors) ? s.errors : [];
    return (
      <>
        <p className="mt-1 text-muted">
          {s.cpsc_notices ?? 0} recall notices checked · {s.pages ?? 0} web pages · {s.findings ?? 0} findings
          {errors.length > 0 && ` · ${errors.length} source${errors.length === 1 ? '' : 's'} failed`}
        </p>
        {errors.length > 0 && <ul className="mt-1 list-disc pl-5 text-danger">{errors.map((e) => <li key={e}>{sentence(e)}</li>)}</ul>}
      </>
    );
  }
  const failed = typeof s.errors === 'number' ? s.errors : 0;
  return (
    <p className="mt-1 text-muted">
      {s.fetched ?? 0} fetched · {s.new ?? 0} new · {s.changed ?? 0} changed · {s.unchanged ?? 0} unchanged · {s.products_rescreened ?? 0} products re-screened
      {failed > 0 && ` · ${failed} failed`}
    </p>
  );
}

function JobRow({ j }: { j: Job }) {
  const listsErrors = research(j) && Array.isArray(j.stats?.errors) && j.stats.errors.length > 0;
  return (
    <li className="px-5 py-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-medium">
          {research(j) ? (
            <>Product research{j.params.reread ? ' (re-reading an earlier run)' : ''}{j.params.product_id && <> · <Link className="text-action hover:underline" to={`/products/${j.params.product_id}`}>open the product</Link></>}</>
          ) : (
            <>{j.source.toUpperCase()} recall import · {j.params.date_start ?? 'last 30 days'}{j.params.date_end ? ` to ${j.params.date_end}` : ''}</>
          )}
          {/* The separator is text, not margin, so the line reads "last 30 days · by hand" (DEF-120). */}
          <span className="text-xs font-normal text-muted">{' · '}{startedBy(j)} · {new Date(j.created_at).toLocaleString()}</span>
        </p>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${TONE[j.status] ?? TONE.queued}`}>{j.status}</span>
      </div>
      {!active(j) && j.status !== 'failed' && <Summary j={j} />}
      {j.error && !listsErrors && <p className="mt-1 text-danger">{j.error.split(/;\s*/).map(sentence).join(' ')}</p>}
    </li>
  );
}

export function DataSources() {
  const { me, loading } = useAuth();
  const admin = me?.role === 'admin';
  const jobs = useLoad(() => (admin ? api<Job[]>('/jobs') : Promise.resolve([])), [admin]);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const running = !!jobs.data?.some(active);
  const { reload } = jobs;

  // While a job is queued or running, look again every two seconds.
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => void reload(), 2000);
    return () => clearInterval(timer);
  }, [running, reload]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post('/ingest', { source: 'cpsc', date_start: start || null, date_end: end || null });
      await reload();
    } catch (err) {
      setError(explain(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Admin" title="Data sources">
        Recall notices are fetched from the US Consumer Product Safety Commission every night. Start a run by hand to bring in a different period.
      </PageTitle>
      {!loading && !admin && <Notice>This page is for administrators.</Notice>}
      {admin && (
        <>
          <form onSubmit={submit} className="card flex flex-wrap items-end gap-4" aria-label="Import recall notices">
            <label className="block text-sm">From<input type="date" className="field mt-1" value={start} onChange={(e) => setStart(e.target.value)} /></label>
            <label className="block text-sm">To<input type="date" className="field mt-1" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
            <button className="btn" disabled={busy || running}>{running ? 'Importing…' : 'Import recall notices'}</button>
            <p className="basis-full text-xs text-muted">Leave the dates empty for the last 30 days. A notice that has not changed is skipped.</p>
          </form>
          {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}
          {jobs.error && <div className="mt-6"><Notice tone="error">{jobs.error} <button className="font-semibold underline" onClick={() => void reload()}>Try again</button></Notice></div>}
          {[
            { title: 'Recall imports', list: jobs.data?.filter((j) => !research(j)), none: 'No import yet.' },
            { title: 'Product research runs', list: jobs.data?.filter(research), none: 'No product has been researched yet.' },
          ].map((g) => (
            <section key={g.title} className="mt-10">
              <h2 className="text-xl font-semibold">{g.title}</h2>
              {g.list?.length === 0 && <p className="mt-3 text-sm text-muted">{g.none}</p>}
              {!!g.list?.length && <ul className="mt-3 divide-y divide-line rounded-3xl border border-line">{g.list.map((j) => <JobRow key={j.id} j={j} />)}</ul>}
            </section>
          ))}
        </>
      )}
    </div>
  );
}
