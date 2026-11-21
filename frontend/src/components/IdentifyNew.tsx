import { ArrowRight, Camera, Loader2, PencilLine, ShieldCheck, Sparkles, TriangleAlert } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { explain, post, type ProductSummary } from '../lib/api';
import { useAuth } from '../lib/auth';

type Suggestion = {
  request_id: string; brand: string | null; name: string | null; model: string | null;
  category: string; confidence: number; similar: ProductSummary[];
};
const CATEGORIES: [string, string][] = [
  ['household', 'Household'], ['food', 'Food and drink'], ['appliances', 'Appliances'], ['electronics', 'Electronics'],
  ['smartphones', 'Smartphones'], ['power_adapters', 'Chargers and power adapters'], ['blenders', 'Blenders'],
  ['mini_fridges', 'Mini-fridges'], ['window_ac', 'Window air conditioners'],
];

/** Shrinks a photo in the browser to at most 1280 px, as JPEG: the model needs the text on the pack,
    not 12 megapixels, and the provider takes at most 4 MB. */
async function shrink(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', 0.85);
}

/** A product no database knows: a photo gives a suggestion, the member checks it, then it is added. */
export function IdentifyNew({ barcode, onCancel }: { barcode: string | null; onCancel: () => void }) {
  const { me } = useAuth();
  const navigate = useNavigate();
  const [preview, setPreview] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [form, setForm] = useState({ name: '', brand: '', model: '', category: 'household' });
  const [busy, setBusy] = useState(false);
  const [manual, setManual] = useState(false);
  const member = !!me && me.verification_level >= 1;

  const read = async (file: File) => {
    setReading(true);
    setSuggestion(null);
    try {
      const image = await shrink(file);
      setPreview(image);
      const s = await post<Suggestion>('/identify/photo', { image, barcode });
      setSuggestion(s);
      setForm({ name: s.name ?? '', brand: s.brand ?? '', model: s.model ?? '', category: s.category });
      setManual(true);
    } catch (e) {
      toast.error(explain(e));
    } finally {
      setReading(false);
    }
  };

  const confirm = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await post<{ slug: string; new: boolean }>('/identify/confirm', {
        name: form.name.trim(), brand: form.brand.trim() || null, model: form.model.trim() || null,
        category: form.category, barcode, request_id: suggestion?.request_id ?? null,
      });
      toast.success(r.new ? 'Added to the registry and screened' : 'Already in the registry');
      navigate(`/products/${r.slug}`);
    } catch (err) {
      toast.error(explain(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="card space-y-6 !p-8">
      <div className="flex items-start gap-4">
        <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-gold-tint text-amber-600"><Sparkles className="size-6" /></span>
        <div>
          <h2 className="font-display text-2xl font-bold">New to Telcron: tell us what it is</h2>
          <p className="mt-1 text-sm text-muted">
            {barcode ? <>No product database knows barcode <span className="font-mono">{barcode}</span> yet. </> : null}
            Take a photo of the front of the pack and we will read it, or type the details. Once you confirm, it gets a permanent record and is screened against recalls.
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
          <div className="grid gap-4 sm:grid-cols-2">
            <label className={`group relative flex cursor-pointer flex-col items-center justify-center gap-3 overflow-hidden rounded-3xl border-2 border-dashed p-6 text-center transition ${reading ? 'border-action bg-action-tint' : 'border-line hover:border-action hover:bg-action-tint/50'}`}>
              {preview ? <img src={preview} alt="Your photo" className="h-36 w-full rounded-2xl object-contain" /> : <Camera className="size-10 text-action" />}
              <span className="text-sm font-semibold">{reading ? 'Reading the packaging…' : preview ? 'Use a different photo' : 'Photograph the front of the pack'}</span>
              {reading && <Loader2 className="absolute right-4 top-4 size-5 animate-spin text-action" />}
              <input type="file" accept="image/*" capture="environment" className="sr-only" disabled={reading} onChange={(e) => e.target.files?.[0] && void read(e.target.files[0])} />
            </label>
            <button onClick={() => setManual(true)} className="flex flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed border-line p-6 text-center transition hover:border-ink/30 hover:bg-panel">
              <PencilLine className="size-10 text-muted" />
              <span className="text-sm font-semibold">Type the details instead</span>
            </button>
          </div>

          <AnimatePresence>
            {suggestion && suggestion.similar.length > 0 && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="overflow-hidden">
                <p className="text-sm font-semibold">Is it one of these? They are already in the registry.</p>
                <ul className="mt-2 grid gap-2 sm:grid-cols-2">
                  {suggestion.similar.map((p) => (
                    <li key={p.id}><Link to={`/products/${p.slug}`} className="flex items-center justify-between rounded-2xl border border-line p-3 text-sm transition hover:border-action hover:shadow-soft">
                      <span><span className="block font-medium">{p.name}</span><span className="text-xs text-muted">{p.brand}</span></span><ArrowRight className="size-4 text-muted" />
                    </Link></li>
                  ))}
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
                    This is what the AI read from your photo ({Math.round(suggestion.confidence * 100)}% sure). It can be wrong, so check every field against the pack.
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

