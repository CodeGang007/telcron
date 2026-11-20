import { useState, type FormEvent } from 'react';
import { api, explain, post } from '../lib/api';
import { useLoad } from '../lib/useLoad';
import { Notice } from './ui';

type Message = { tone: 'ok' | 'error'; text: string } | null;

/** Report a hazard on a product. The safety team decides; coins follow a confirmed report. */
export function FlagForm({ slug }: { slug: string }) {
  const dimensions = useLoad(() => api<{ code: string; name: string }[]>('/hazard-dimensions'), []);
  const [dimension, setDimension] = useState('');
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Message>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await post(`/products/${slug}/flags`, { dimension_code: dimension || null, description });
      setMsg({ tone: 'ok', text: 'Report sent to the safety team. You earn 25 TelCoins if it is confirmed.' });
      setDescription('');
    } catch (err) {
      setMsg({ tone: 'error', text: explain(err) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="card space-y-4" aria-label="Report a hazard">
      <h3 className="font-semibold">Report a hazard</h3>
      <label className="block text-sm">
        Kind of hazard
        <select className="field mt-1" value={dimension} onChange={(e) => setDimension(e.target.value)}>
          <option value="">Not sure</option>
          {dimensions.data?.map((d) => (
            <option key={d.code} value={d.code}>{d.name}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        What happened (at least 20 characters)
        <textarea className="field mt-1 min-h-24" required minLength={20} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <button className="btn-ghost" disabled={busy}>{busy ? 'Sending…' : 'Send report'}</button>
    </form>
  );
}

const FIELDS = [
  { value: 'canonical_name', label: 'Product name' },
  { value: 'model_number', label: 'Model number' },
  { value: 'description', label: 'Description' },
];

/** Suggest a correction to what the registry says about a product. */
export function FactForm({ slug }: { slug: string }) {
  const [attribute, setAttribute] = useState('model_number');
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Message>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await post(`/products/${slug}/fact-reports`, { attribute, proposed_value: value });
      setMsg({ tone: 'ok', text: 'Correction sent for review. You earn 20 TelCoins if it is accepted.' });
      setValue('');
    } catch (err) {
      setMsg({ tone: 'error', text: explain(err) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="card space-y-4" aria-label="Suggest a correction">
      <h3 className="font-semibold">Suggest a correction</h3>
      <label className="block text-sm">
        What is wrong
        <select className="field mt-1" value={attribute} onChange={(e) => setAttribute(e.target.value)}>
          {FIELDS.map((f) => (
            <option key={f.value} value={f.value}>{f.label}</option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        What it should say
        <input className="field mt-1" required maxLength={500} value={value} onChange={(e) => setValue(e.target.value)} />
      </label>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <button className="btn-ghost" disabled={busy}>{busy ? 'Sending…' : 'Send correction'}</button>
    </form>
  );
}
