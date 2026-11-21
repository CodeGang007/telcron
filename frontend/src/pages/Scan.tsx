import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';
import { BarcodeFormat, DecodeHintType } from '@zxing/library';
import { Camera, CameraOff, Hash, ImageUp, Keyboard, Loader2, ScanLine, Sparkles } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Notice, PageTitle } from '../components/ui';
import { IdentifyNew } from '../components/IdentifyNew';
import { ApiError, explain, post } from '../lib/api';

type Identified = { slug: string; name: string; new: boolean };
type Phase = 'idle' | 'camera' | 'looking' | 'error' | 'unknown';

// Retail barcodes only: a QR code or a shipping label on the same box is not the product.
const RETAIL = [BarcodeFormat.EAN_13, BarcodeFormat.EAN_8, BarcodeFormat.UPC_A, BarcodeFormat.UPC_E];
const reader = () => new BrowserMultiFormatReader(new Map<DecodeHintType, unknown>([[DecodeHintType.POSSIBLE_FORMATS, RETAIL], [DecodeHintType.TRY_HARDER, true]]));

const STAGES = ['Reading the barcode', 'Finding the product', 'Checking recall notices', 'Scoring hazards', 'Issuing the passport'];

export function Scan() {
  const navigate = useNavigate();
  const video = useRef<HTMLVideoElement>(null);
  const controls = useRef<IScannerControls | null>(null);
  const busy = useRef(false);
  const [phase, setPhase] = useState<Phase>('idle');
  const [stage, setStage] = useState(0);
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [unknown, setUnknown] = useState<string | null>(null);

  const stopCamera = useCallback(() => {
    controls.current?.stop();
    controls.current = null;
  }, []);
  useEffect(() => stopCamera, [stopCamera]);

  const identify = useCallback(async (barcode: string) => {
    if (busy.current) return;
    busy.current = true;
    stopCamera();
    setPhase('looking');
    setError(null);
    setStage(0);
    const timer = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 650);
    try {
      const found = await post<Identified>('/identify', { barcode: barcode.replace(/[\s-]/g, '') });
      toast.success(found.new ? 'New product added and screened' : 'Product found', { description: found.name });
      navigate(`/products/${found.slug}`);
    } catch (e) {
      if (e instanceof ApiError && e.code === 'product_not_identified') {
        setUnknown(barcode.replace(/[\s-]/g, ''));
        setPhase('unknown');
        return;
      }
      setError(`${explain(e)} (read: ${barcode})`);
      setPhase('error');
    } finally {
      clearInterval(timer);
      busy.current = false;
    }
  }, [navigate, stopCamera]);

  const startCamera = async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('This browser cannot open the camera. Type the number under the barcode instead.');
      setPhase('error');
      return;
    }
    setPhase('camera');
    try {
      controls.current = await reader().decodeFromVideoDevice(undefined, video.current!, (result) => {
        if (result) void identify(result.getText());
      });
    } catch {
      setError('The camera could not be opened. Allow camera access, or type the number under the barcode.');
      setPhase('error');
    }
  };

  const fromPhoto = async (file: File) => {
    const url = URL.createObjectURL(file);
    try {
      const result = await reader().decodeFromImageUrl(url);
      void identify(result.getText());
    } catch {
      setError('No barcode could be read in that photo. Try a sharper, closer picture.');
      setPhase('error');
    } finally {
      URL.revokeObjectURL(url);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (code.trim()) void identify(code.trim());
  };

  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Scan" title="Scan a barcode" icon={ScanLine}>
        Point your camera at the barcode on the box. We find the product, check it against recall notices and certificates, and show you its passport.
      </PageTitle>

      {phase === 'unknown' ? (
        <IdentifyNew barcode={unknown} onCancel={() => { setUnknown(null); setPhase('idle'); }} />
      ) : (
      <div className="grid gap-8 lg:grid-cols-[1.3fr_1fr]">
        <div className="relative aspect-[4/3] overflow-hidden rounded-[2rem] bg-night shadow-lift">
          <video ref={video} className={`h-full w-full object-cover ${phase === 'camera' ? '' : 'hidden'}`} muted playsInline />
          {phase !== 'camera' && <div className="bg-grid absolute inset-0" />}

          {phase === 'camera' && (
            <div className="pointer-events-none absolute inset-0 grid place-items-center">
              <div className="relative h-[46%] w-[72%] rounded-3xl border-2 border-white/30">
                {['left-0 top-0 border-l-4 border-t-4 rounded-tl-3xl', 'right-0 top-0 border-r-4 border-t-4 rounded-tr-3xl', 'left-0 bottom-0 border-l-4 border-b-4 rounded-bl-3xl', 'right-0 bottom-0 border-r-4 border-b-4 rounded-br-3xl'].map((c) => (
                  <span key={c} className={`absolute size-10 border-brand-bright ${c}`} />
                ))}
                <span className="absolute inset-x-3 h-0.5 animate-scan rounded-full bg-brand-bright shadow-[0_0_18px_4px] shadow-brand-bright/70" />
              </div>
              <p className="absolute bottom-6 rounded-full bg-black/50 px-4 py-2 text-sm text-white backdrop-blur">Hold the barcode inside the frame</p>
            </div>
          )}

          <AnimatePresence>
            {phase === 'idle' && (
              <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 grid place-items-center p-8 text-center text-white">
                <div>
                  <span className="relative mx-auto grid size-24 place-items-center rounded-full bg-gradient-to-br from-brand-bright to-brand-deep shadow-2xl">
                    <span className="absolute inset-0 rounded-full bg-brand-bright/40 animate-pulse-ring" />
                    <Camera className="size-10" />
                  </span>
                  <p className="mt-6 font-display text-2xl font-bold">Ready when you are</p>
                  <p className="mt-2 text-sm text-white/60">Your camera is only used here, to read the barcode. Nothing is recorded.</p>
                  <button className="btn-brand mt-6" onClick={startCamera}><Camera className="size-4" />Start camera</button>
                </div>
              </motion.div>
            )}
            {phase === 'looking' && (
              <motion.div key="looking" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 grid place-items-center bg-night/80 p-8 text-white backdrop-blur-md">
                <div className="w-full max-w-xs">
                  <Sparkles className="mx-auto size-10 text-gold" />
                  <ol className="mt-6 space-y-3">
                    {STAGES.map((s, i) => (
                      <motion.li key={s} initial={{ opacity: 0, x: -8 }} animate={{ opacity: i <= stage ? 1 : 0.35, x: 0 }} transition={{ delay: i * 0.05 }} className="flex items-center gap-3 text-sm">
                        {i < stage ? <span className="grid size-5 place-items-center rounded-full bg-ok text-[10px]">✓</span> : i === stage ? <Loader2 className="size-5 animate-spin text-brand-bright" /> : <span className="size-5 rounded-full border border-white/30" />}
                        {s}
                      </motion.li>
                    ))}
                  </ol>
                </div>
              </motion.div>
            )}
            {phase === 'error' && (
              <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 grid place-items-center p-8 text-center text-white">
                <div>
                  <CameraOff className="mx-auto size-12 text-rose-300" />
                  <p className="mx-auto mt-4 max-w-sm text-sm text-white/80">{error}</p>
                  <button className="btn-brand mt-6" onClick={startCamera}><Camera className="size-4" />Try the camera again</button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          {phase === 'camera' && (
            <button className="absolute right-4 top-4 rounded-full bg-black/50 px-4 py-2 text-xs font-semibold text-white backdrop-blur" onClick={() => { stopCamera(); setPhase('idle'); }}>
              Stop
            </button>
          )}
        </div>

        <div className="space-y-6">
          <form onSubmit={submit} className="card space-y-4" aria-label="Type a barcode">
            <h2 className="flex items-center gap-2 font-display text-lg font-bold"><Keyboard className="size-5 text-brand-ink" />Type the number</h2>
            <p className="text-sm text-muted">The digits printed under the barcode: 8, 12 or 13 of them.</p>
            <label className="sr-only" htmlFor="barcode">Barcode number</label>
            <div className="relative">
              <Hash className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <input id="barcode" className="field !pl-10 font-mono tracking-wider" inputMode="numeric" pattern="[0-9 \-]{6,20}" placeholder="0 12345 67890 5" value={code} onChange={(e) => setCode(e.target.value)} />
            </div>
            <button className="btn w-full" disabled={phase === 'looking' || !code.trim()}>Look it up</button>
          </form>

          <label className="card card-hover flex cursor-pointer items-center gap-4">
            <span className="grid size-12 place-items-center rounded-2xl bg-action-tint text-action"><ImageUp className="size-6" /></span>
            <span>
              <span className="block font-semibold">Use a photo instead</span>
              <span className="text-sm text-muted">Pick a clear picture of the barcode.</span>
            </span>
            <input type="file" accept="image/*" className="sr-only" onChange={(e) => e.target.files?.[0] && void fromPhoto(e.target.files[0])} />
          </label>

          {error && phase !== 'error' && <Notice tone="error">{error}</Notice>}
          <p className="text-xs text-muted">New products are looked up in UPCitemdb and the Open Food, Beauty and Products Facts databases. If none knows it, you can identify it from a photo.</p>
        </div>
      </div>
      )}
    </div>
  );
}
