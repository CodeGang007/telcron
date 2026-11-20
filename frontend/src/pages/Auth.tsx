import { useState, type FormEvent } from 'react';
import { BellRing, Coins, ShieldCheck } from 'lucide-react';
import { motion } from 'motion/react';
import { Link, useNavigate } from 'react-router-dom';
import { LogoMark } from '../components/Logo';
import { Notice } from '../components/ui';
import { explain, post } from '../lib/api';
import { useAuth } from '../lib/auth';

function Shell({ title, sub, children }: { title: string; sub: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-[calc(100vh-4rem)] lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-night p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="bg-grid absolute inset-0 opacity-70" />
        <motion.div className="absolute -left-32 -top-32 size-[480px] rounded-full bg-brand-ink/50 blur-[110px]" animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 12, repeat: Infinity }} />
        <motion.div className="absolute -bottom-32 right-0 size-[420px] rounded-full bg-action/40 blur-[110px]" animate={{ scale: [1.1, 1, 1.1] }} transition={{ duration: 14, repeat: Infinity }} />
        <LogoMark size={48} className="relative" />
        <div className="relative">
          <h2 className="font-display text-4xl font-extrabold leading-tight">One verified identity signs everything you contribute.</h2>
          <ul className="mt-8 space-y-4 text-white/80">
            {[
              [ShieldCheck, 'Your reviews and hazard reports carry your TelcronID'],
              [BellRing, 'Alerts when a product you own is recalled'],
              [Coins, 'TelCoins, levels and badges for contributions that help'],
            ].map(([Icon, text]) => {
              const I = Icon as typeof ShieldCheck;
              return <li key={text as string} className="flex items-center gap-3"><span className="glass grid size-10 place-items-center rounded-xl"><I className="size-5" /></span>{text as string}</li>;
            })}
          </ul>
        </div>
        <p className="relative text-xs text-white/50">Telcron never sells your data. Identity documents are deleted after the check.</p>
      </div>
      <div className="grid place-items-center px-4 py-12">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
          <h1 className="font-display text-3xl font-extrabold tracking-tight">{title}</h1>
          <p className="mt-2 text-muted">{sub}</p>
          <div className="mt-8">{children}</div>
        </motion.div>
      </div>
    </div>
  );
}

function Field(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  const { label, hint, ...input } = props;
  return (
    <label className="block text-sm font-medium">
      {label}
      <input className="field mt-1 font-normal" {...input} />
      {hint && <span className="mt-1 block text-xs font-normal text-muted">{hint}</span>}
    </label>
  );
}

export function SignIn() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
      navigate('/');
    } catch (err) {
      setError(explain(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Shell title="Sign in" sub="Use your TelcronID.">
      <form onSubmit={submit} className="space-y-5">
        <Field label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Field label="Password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <Notice tone="error">{error}</Notice>}
        <button className="btn w-full !py-3.5" disabled={busy}>{busy ? 'Signing in…' : 'Sign In'}</button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        New to Telcron? <Link className="text-action" to="/sign-up">Create your TelcronID</Link>
      </p>
    </Shell>
  );
}

type Registered = { dev_codes: Record<string, string> | null };

export function SignUp() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ display_name: '', email: '', phone_e164: '', password: '' });
  const [registered, setRegistered] = useState<Registered | null>(null);
  const [codes, setCodes] = useState({ email: '', phone: '' });
  const [done, setDone] = useState({ email: false, phone: false });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const register = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setRegistered(await post<Registered>('/auth/register', form));
    } catch (err) {
      setError(explain(err));
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const next = { ...done };
      for (const channel of ['email', 'phone'] as const) {
        if (next[channel]) continue;
        await post('/auth/verify', { email: form.email, channel, code: codes[channel] });
        next[channel] = true;
        setDone({ ...next });
      }
      await signIn(form.email, form.password);
      navigate('/rewards');
    } catch (err) {
      setError(explain(err));
    } finally {
      setBusy(false);
    }
  };

  if (!registered)
    return (
      <Shell title="Create your TelcronID" sub="One verified identity signs everything you contribute.">
        <form onSubmit={register} className="space-y-5">
          <Field label="Name" required minLength={2} maxLength={80} autoComplete="name" value={form.display_name} onChange={set('display_name')} />
          <Field label="Email" type="email" required autoComplete="email" value={form.email} onChange={set('email')} />
          <Field label="Mobile number" type="tel" required pattern="\+[1-9][0-9]{7,14}" placeholder="+14155550123" hint="With country code, for example +14155550123." autoComplete="tel" value={form.phone_e164} onChange={set('phone_e164')} />
          <Field label="Password" type="password" required minLength={10} hint="At least 10 characters." autoComplete="new-password" value={form.password} onChange={set('password')} />
          {error && <Notice tone="error">{error}</Notice>}
          <button className="btn w-full !py-3.5" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</button>
        </form>
        <p className="mt-6 text-center text-sm text-muted">
          Already have one? <Link className="text-action" to="/sign-in">Sign in</Link>
        </p>
      </Shell>
    );

  return (
    <Shell title="Confirm your email and phone" sub="Enter both six-digit codes to reach Level 1 and earn 100 TelCoins.">
      <form onSubmit={verify} className="space-y-5">
        {registered.dev_codes && (
          <Notice>
            Development build: codes are not sent yet. Email {registered.dev_codes.email}, phone {registered.dev_codes.phone}.
          </Notice>
        )}
        <Field label={`Code sent to ${form.email}`} inputMode="numeric" pattern="[0-9]{6}" required disabled={done.email} value={codes.email} onChange={(e) => setCodes({ ...codes, email: e.target.value })} />
        <Field label={`Code sent to ${form.phone_e164}`} inputMode="numeric" pattern="[0-9]{6}" required disabled={done.phone} value={codes.phone} onChange={(e) => setCodes({ ...codes, phone: e.target.value })} />
        {error && <Notice tone="error">{error}</Notice>}
        <button className="btn w-full !py-3.5" disabled={busy}>{busy ? 'Checking…' : 'Confirm and continue'}</button>
      </form>
    </Shell>
  );
}
