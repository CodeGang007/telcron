import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Notice, PageTitle } from '../components/ui';
import { ApiError, api, explain, post } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useLoad } from '../lib/useLoad';

type Subject = {
  description?: string | null;
  dimension_code?: string | null;
  reporter?: string;
  reporter_trust?: number;
  attribute?: string;
  current_value?: string | null;
  proposed_value?: string | null;
  is_confirmation?: boolean;
  reason?: string;
  member?: string;
  product?: { slug: string; name: string };
};
type Task = {
  id: string; task_type: string; status: string; priority: number; created_at: string; subject: Subject;
  /** Not sent by the API yet (DEF-101): the subject is the caller's own contribution or coins. */
  mine?: boolean;
};

// What each decision means differs by the kind of task, so the buttons say it in words.
const KIND: Record<string, { title: string; confirm: string; reject: string }> = {
  hazard_flag: { title: 'Hazard report', confirm: 'Confirm hazard', reject: 'Not a hazard' },
  fact_report: { title: 'Correction', confirm: 'Accept correction', reject: 'Reject correction' },
  fraud_hold: { title: 'Coins on hold', confirm: 'Confirm fraud', reject: 'Release coins' },
  hazard_insufficient_data: { title: 'Score missing evidence', confirm: 'Mark reviewed', reject: '' },
};

function TaskCard({ task, onDone }: { task: Task; onDone: () => void }) {
  const kind = KIND[task.task_type] ?? { title: task.task_type.replace(/_/g, ' '), confirm: 'Mark reviewed', reject: '' };
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Nobody decides on their own item (DEF-011). Until the queue says so up front, a 403 own_item
  // also takes the buttons away, so the reviewer is not left with decisions that can only fail.
  const [own, setOwn] = useState(!!task.mine);
  const s = task.subject;
  const decide = async (decision: 'confirm' | 'reject' | 'dismiss') => {
    setBusy(true);
    setError(null);
    try {
      await post(`/review-tasks/${task.id}/resolve`, { decision, note: note || null });
      onDone();
    } catch (e) {
      if (e instanceof ApiError && e.code === 'own_item') setOwn(true);
      else setError(explain(e));
      setBusy(false);
    }
  };
  return (
    <li className="card">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="eyebrow">{kind.title}</p>
        <p className="text-xs text-muted">{new Date(task.created_at).toLocaleString()}</p>
      </div>
      {s.product && (
        <Link to={`/products/${s.product.slug}`} className="mt-2 block font-semibold hover:text-action">{s.product.name}</Link>
      )}
      {task.task_type === 'hazard_flag' && (
        <>
          <p className="mt-2 text-sm">{s.description}</p>
          <p className="mt-2 text-xs text-muted">
            Reported by {s.reporter} (trust {s.reporter_trust}){s.dimension_code ? ` · ${s.dimension_code.replace('safety.', '').replace(/_/g, ' ')}` : ''}
          </p>
        </>
      )}
      {task.task_type === 'fact_report' && (
        <dl className="mt-2 grid gap-1 text-sm">
          <div><dt className="inline text-muted">Field: </dt><dd className="inline">{s.attribute?.replace(/_/g, ' ')}</dd></div>
          <div><dt className="inline text-muted">Now: </dt><dd className="inline">{s.current_value ?? '—'}</dd></div>
          <div><dt className="inline text-muted">Proposed: </dt><dd className="inline font-medium">{s.is_confirmation ? 'confirms the current value' : s.proposed_value}</dd></div>
          <div className="text-xs text-muted">From {s.reporter}</div>
        </dl>
      )}
      {task.task_type === 'fraud_hold' && (
        <p className="mt-2 text-sm">{s.member}: {s.reason}</p>
      )}
      {own ? (
        <div className="mt-4"><Notice>Your item: a colleague decides this.</Notice></div>
      ) : (
        <>
          <label className="mt-4 block text-sm">
            Note (optional)
            <input className="field mt-1" maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          {error && <div className="mt-3"><Notice tone="error">{error}</Notice></div>}
          <div className="mt-4 flex flex-wrap gap-3">
            <button className="btn min-h-11 !px-4 !py-2" disabled={busy} onClick={() => decide('confirm')}>{kind.confirm}</button>
            {kind.reject && <button className="btn-ghost min-h-11 !px-4 !py-2" disabled={busy} onClick={() => decide('reject')}>{kind.reject}</button>}
            <button className="btn-ghost min-h-11 !px-4 !py-2" disabled={busy} onClick={() => decide('dismiss')}>Dismiss</button>
          </div>
        </>
      )}
    </li>
  );
}

export function ReviewQueue() {
  const { me, loading } = useAuth();
  const staff = !!me && (me.role === 'admin' || me.role === 'moderator');
  const tasks = useLoad(() => (staff ? api<Task[]>('/review-tasks') : Promise.resolve([])), [staff]);
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Safety team" title="Review queue">
        Reports, corrections and holds waiting for a decision. Most urgent first.
      </PageTitle>
      {!loading && !staff && <Notice>This page is for the safety team.</Notice>}
      {tasks.error && <Notice tone="error">{tasks.error}</Notice>}
      {staff && tasks.data?.length === 0 && <Notice tone="ok">Nothing is waiting.</Notice>}
      <ul className="space-y-4">
        {tasks.data?.map((t) => (
          <TaskCard key={t.id} task={t} onDone={() => void tasks.reload()} />
        ))}
      </ul>
    </div>
  );
}
