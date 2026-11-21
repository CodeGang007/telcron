import { ArrowRight, Camera, Check, Link2, Loader2, PencilLine, ScanText, ShieldCheck, Sparkles, TriangleAlert, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { explain, post, type ProductSummary } from '../lib/api';
import { useAuth } from '../lib/auth';
import { track } from '../lib/researching';

type Suggestion = {
  request_id: string; brand: string | null; name: string | null; model: string | null;
  category: string; confidence: number; similar: ProductSummary[];
  likely_same: string | null; read_text: string[]; looks_like: string[];
};
const SIDES = ['Front of the pack', 'Back or ingredients label', 'Model plate or rating label', 'Anything else printed'];
const CATEGORIES: [string, string][] = [
  ['household', 'Household'], ['food', 'Food and drink'], ['appliances', 'Appliances'], ['electronics', 'Electronics'],
  ['smartphones', 'Smartphones'], ['power_adapters', 'Chargers and power adapters'], ['blenders', 'Blenders'],
  ['mini_fridges', 'Mini-fridges'], ['window_ac', 'Window air conditioners'],
];

/** Shrinks a photo in the browser to at most 1280 px, as JPEG: the model needs the text on the pack,
    not 12 megapixels, and the provider takes at most 4 MB. */
async function shrink(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1024 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', 0.85);
}

function Steps({ at }: { at: number }) {
  const steps = ['Barcode', 'Photos', 'Check details', 'Research'];
  return (
    <ol className="flex items-center gap-2 text-xs font-semibold" aria-label="Progress">
      {steps.map((s, i) => (
        <li key={s} className="flex flex-1 items-center gap-2" aria-current={i === at ? 'step' : undefined}>
          <span className={`grid size-6 shrink-0 place-items-center rounded-full transition ${i < at ? 'bg-ok text-white' : i === at ? 'bg-ink text-white' : 'bg-panel text-muted'}`}>
            {i < at ? <Check className="size-3.5" /> : i + 1}
          </span>
          <span className={`hidden sm:inline ${i <= at ? 'text-ink' : 'text-muted'}`}>{s}</span>
          {i < steps.length - 1 && <span className={`h-px flex-1 ${i < at ? 'bg-ok' : 'bg-line'}`} />}
        </li>
      ))}
    </ol>
  );
}

/** A product no database knows: a photo gives a suggestion, the member checks it, then it is added. */
export function IdentifyNew({ barcode, onCancel }: { barcode: string | null; onCancel: () => void }) {
  const { me } = useAuth();
  const navigate = useNavigate();
  const [shots, setShots] = useState<(string | null)[]>([null, null, null, null]);
  const [reading, setReading] = useState(false);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [form, setForm] = useState({ name: '', brand: '', model: '', category: 'household' });
  const [busy, setBusy] = useState(false);
  const [manual, setManual] = useState(false);
  const member = !!me && me.verification_level >= 1;

  const taken = shots.filter((x): x is string => !!x);
  const take = async (i: number, file: File) => {
    try {
      const image = await shrink(file);
      setShots((prev) => prev.map((v, j) => (j === i ? image : v)));
      setSuggestion(null);
    } catch {
      toast.error('That photo could not be opened. Try another.');
    }
  };
  const read = async () => {
    setReading(true);
    setSuggestion(null);
    try {
      const s = await post<Suggestion>('/identify/photo', { images: taken, barcode });
      setSuggestion(s);
      setForm({ name: s.name ?? '', brand: s.brand ?? '', model: s.model ?? '', category: s.category });
      setManual(true);
    } catch (e) {
      toast.error(explain(e));
    } finally {
      setReading(false);
    }
  };

  const confirm = async (e: FormEvent | null, existing: string | null = null) => {
    e?.preventDefault();
    setBusy(true);
    try {
      const r = await post<{ slug: string; new: boolean; linked: boolean }>('/identify/confirm', {
        name: form.name.trim().length >= 3 ? form.name.trim() : (suggestion?.name ?? 'Product'),
        brand: form.brand.trim() || null, model: form.model.trim() || null,
        category: form.category, barcode, request_id: suggestion?.request_id ?? null, existing,
      });
      toast.success(
        r.new ? 'Added, screened, and now being researched' : r.linked ? 'Linked to the product already in the registry' : 'Already in the registry',
        { description: r.new ? 'We are searching recall registries and the web for it.' : undefined },
      );
      if (r.new) track(r.slug, form.name.trim() || 'your product');
      navigate(`/products/${r.slug}`);
    } catch (err) {
      toast.error(explain(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="card space-y-6 !p-8">
      <Steps at={busy ? 3 : suggestion || manual ? 2 : taken.length ? 1 : barcode ? 1 : 0} />
      <div className="flex items-start gap-4">
        <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-gold-tint text-gold-deep"><Sparkles className="size-6" /></span>
        <div>
          <h2 className="font-display text-2xl font-bold">New to Telcron: tell us what it is</h2>
          <p className="mt-1 text-sm text-muted">
            {barcode ? <>No product database knows barcode <span className="font-mono">{barcode}</span> yet. </> : null}
            Photograph it from a few sides and we will read the pack, or type the details. Once you confirm, it gets a permanent record, and we search official recall registries and the web for anything about its safety.
          </p>
        </div>
      </div>

      {!member ? (
        <div className="rounded-2xl bg-panel p-5 text-sm">
          <p className="font-semibold">Adding a product needs a verified TelcronID.</p>
          <p className="mt-1 text-muted">That keeps the registry trustworthy: every new product is signed by a real person.</p>
          <div className="mt-4 flex gap-3"><Link to="/sign-in" className="btn btn-sm">Sign in</Link><button className="btn-ghost btn-sm" onClick={onCancel}>Scan something else</button></div>
        </div>
      ) : (
        <>
          <div>
            <p className="text-sm font-semibold">Photograph it from up to four sides</p>
            <p className="text-xs text-muted">The more of the pack we can read (brand, model, label), the surer the match. One photo is enough to start.</p>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {SIDES.map((side, i) => (
                <label key={side} className={`group relative flex aspect-square cursor-pointer flex-col items-center justify-center gap-2 overflow-hidden rounded-3xl border-2 border-dashed p-3 text-center transition ${shots[i] ? 'border-action' : 'border-line hover:border-action hover:bg-action-tint/50'}`}>
                  {shots[i] ? (
                    <>
                      <img src={shots[i]!} alt={side} className="absolute inset-0 size-full object-cover" />
                      <button type="button" aria-label={`Remove ${side}`} onClick={(e) => { e.preventDefault(); setShots((p) => p.map((v, j) => (j === i ? null : v))); setSuggestion(null); }} className="absolute right-2 top-2 grid size-7 place-items-center rounded-full bg-white/90 text-ink shadow-soft"><X className="size-4" /></button>
                    </>
                  ) : (
                    <Camera className="size-7 text-action" />
                  )}
                  <span className={`relative text-xs font-semibold ${shots[i] ? 'rounded-full bg-white/90 px-2 py-0.5' : ''}`}>{side}</span>
                  <input type="file" accept="image/*" capture="environment" className="sr-only" disabled={reading} onChange={(e) => e.target.files?.[0] && void take(i, e.target.files[0])} />
                </label>
              ))}
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <button className="btn" onClick={read} disabled={!taken.length || reading}>
                {reading ? <Loader2 className="size-4 animate-spin" /> : <ScanText className="size-4" />}
                {reading ? 'Reading the packaging…' : `Identify from ${taken.length || 'the'} photo${taken.length === 1 ? '' : 's'}`}
              </button>
              <button className="btn-ghost" onClick={() => setManual(true)}><PencilLine className="size-4" />Type the details instead</button>
            </div>
          </div>

          {suggestion && (suggestion.read_text.length > 0 || suggestion.looks_like.length > 0) && (
            <div className="rounded-2xl bg-panel p-4 text-xs text-muted">
              {suggestion.looks_like.length > 0 && <p><span className="font-semibold text-ink">Looks like:</span> {suggestion.looks_like.join(', ')}</p>}
              {suggestion.read_text.length > 0 && <p className="mt-1"><span className="font-semibold text-ink">Printed on it:</span> {suggestion.read_text.join(' · ')}</p>}
            </div>
          )}

          <AnimatePresence>
            {suggestion && suggestion.similar.length > 0 && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="overflow-hidden">
                <p className="text-sm font-semibold">Is it one of these? They are already in the registry.</p>
                <p className="text-xs text-muted">The same product in another size, colour or pack is one product: {barcode ? 'your barcode is added to it' : 'pick it'} rather than a duplicate.</p>
                <ul className="mt-2 grid gap-2 sm:grid-cols-2">
                  {suggestion.similar.map((p) => {
                    const likely = p.slug === suggestion.likely_same;
                    return (
                      <li key={p.id} className={`rounded-2xl border p-3 text-sm ${likely ? 'border-ok bg-ok-tint/40' : 'border-line'}`}>
                        {likely && <p className="mb-1 flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-ok"><Check className="size-3.5" />Very likely the same product</p>}
                        <span className="block font-medium">{p.name}</span><span className="text-xs text-muted">{[p.brand, p.model_number].filter(Boolean).join(' · ')}</span>
                        <div className="mt-2 flex gap-2">
                          <button className="btn btn-sm" disabled={busy} onClick={() => void confirm(null, p.slug)}><Link2 className="size-3.5" />Yes, it is this one</button>
                          <Link to={`/products/${p.slug}`} className="btn-ghost btn-sm">View<ArrowRight className="size-3.5" /></Link>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {manual && (
              <motion.form initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} onSubmit={confirm} className="space-y-4 overflow-hidden" aria-label="Confirm the product">
                {suggestion && (
                  <p className="flex items-start gap-2 rounded-2xl bg-warn-tint px-4 py-3 text-sm text-warn">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0" />
                    This is what the AI read from your photos ({Math.round(suggestion.confidence * 100)}% sure). It can be wrong, so check every field against the pack.
                  </p>
                )}
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block text-sm font-medium sm:col-span-2">Product name<input className="field mt-1" required minLength={3} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="As printed on the pack" /></label>
                  <label className="block text-sm font-medium">Brand<input className="field mt-1" value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} /></label>
                  <label className="block text-sm font-medium">Model number<input className="field mt-1" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} placeholder="If there is one" /></label>
                  <label className="block text-sm font-medium sm:col-span-2">Category
                    <select className="field mt-1" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                      {CATEGORIES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
                    </select>
                  </label>
                </div>
                <button className="btn w-full" disabled={busy || form.name.trim().length < 3}>
                  {busy ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}{busy ? 'Adding and screening…' : 'Add it and screen it'}
                </button>
              </motion.form>
            )}
          </AnimatePresence>
        </>
      )}
    </motion.div>
  );
}

