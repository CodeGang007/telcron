import { useEffect, useState, type FormEvent } from 'react';
import { Notice, PageTitle } from '../components/ui';
import { api, explain, post } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useLoad } from '../lib/useLoad';

type Job = {
  id: string;
  source: string;
  trigger: string;
  status: string;
  params: { date_start?: string; date_end?: string };
  stats: { fetched?: number; new?: number; changed?: number; unchanged?: number; errors?: number; products_rescreened?: number };
  error: string | null;
  created_at: string;
  finished_at: string | null;
};
const TONE: Record<string, string> = {
  succeeded: 'bg-ok-tint text-ok', partial: 'bg-warn-tint text-warn', failed: 'bg-danger-tint text-danger',
  queued: 'bg-neutral-tint text-muted', running: 'bg-neutral-tint text-muted',
};
const active = (j: Job) => j.status === 'queued' || j.status === 'running';

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
          <h2 className="mt-10 text-xl font-semibold">Runs</h2>
          {jobs.data?.length === 0 && <p className="mt-3 text-sm text-muted">No run yet.</p>}
          <ul className="mt-3 divide-y divide-line rounded-3xl border border-line">
            {jobs.data?.map((j) => (
              <li key={j.id} className="px-5 py-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="font-medium">
                    {j.source.toUpperCase()} · {j.params.date_start ?? 'last 30 days'}{j.params.date_end ? ` to ${j.params.date_end}` : ''}
                    <span className="ml-2 text-xs font-normal text-muted">{j.trigger === 'schedule' ? 'nightly' : 'by hand'} · {new Date(j.created_at).toLocaleString()}</span>
                  </p>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${TONE[j.status] ?? TONE.queued}`}>{j.status}</span>
                </div>
                {!active(j) && j.status !== 'failed' && (
                  <p className="mt-1 text-muted">
                    {j.stats.fetched ?? 0} fetched · {j.stats.new ?? 0} new · {j.stats.changed ?? 0} changed · {j.stats.unchanged ?? 0} unchanged · {j.stats.products_rescreened ?? 0} products re-screened
                    {j.stats.errors ? ` · ${j.stats.errors} failed` : ''}
                  </p>
                )}
                {j.error && <p className="mt-1 text-danger">{j.error}</p>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
