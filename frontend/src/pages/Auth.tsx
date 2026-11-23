import { useState, type FormEvent } from 'react';
import { BellRing, Coins, ShieldCheck } from 'lucide-react';
import { motion } from 'motion/react';
import { Link, useNavigate } from 'react-router-dom';
import { LogoMark } from '../components/Logo';
import { Notice } from '../components/ui';
import { ApiError, explain, post } from '../lib/api';
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
  // Set when the password was right but the email is not confirmed yet: ask for the code.
  const [unverified, setUnverified] = useState(false);
  const [code, setCode] = useState('');
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (err) {
      if (err instanceof ApiError && err.code === 'email_not_verified') setUnverified(true);
      setError(explain(err));
    } finally {
      setBusy(false);
    }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => {
      if (unverified) await post('/auth/verify', { email, channel: 'email', code: code.trim() });
      await signIn(email, password);
      navigate(unverified ? '/rewards' : '/');
    });
  };
  const resend = () => run(async () => {
    const r = await post<{ dev_codes: Record<string, string> | null }>('/auth/resend', { email });
    setNote(`A new code is on its way${r.dev_codes?.email ? ` (development build: ${r.dev_codes.email})` : ''}. Check your spam folder too.`);
  });
  return (
    <Shell title="Sign in" sub="Use your TelcronID.">
      <form onSubmit={submit} className="space-y-5">
        <Field label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => { setEmail(e.target.value); setUnverified(false); }} />
        <Field label="Password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        {unverified && (
          <Field label="Code from the email" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required value={code} onChange={(e) => setCode(e.target.value)} />
        )}
        {error && <Notice tone="error">{error}</Notice>}
        {note && <Notice tone="ok">{note}</Notice>}
        <button className="btn w-full !py-3.5" disabled={busy}>{busy ? 'Signing in…' : unverified ? 'Confirm and sign in' : 'Sign In'}</button>
        {unverified && (
          <p className="text-center text-sm text-muted">No email? <button type="button" className="font-semibold text-action" onClick={resend}>Send a new code</button> (once a minute)</p>
        )}
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        New to Telcron? <Link className="text-action" to="/sign-up">Create your TelcronID</Link>
      </p>
    </Shell>
  );
}

type Registered = { dev_codes: Record<string, string> | null; email_sent: boolean };

export function SignUp() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ display_name: '', email: '', phone_e164: '', password: '' });
  const [registered, setRegistered] = useState<Registered | null>(null);
  const [code, setCode] = useState('');
  const [resent, setResent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const register = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setRegistered(await post<Registered>('/auth/register', { ...form, phone_e164: form.phone_e164.replace(/\s+/g, '') || null }));
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
      await post('/auth/verify', { email: form.email, channel: 'email', code: code.trim() });
      await signIn(form.email, form.password);
      navigate('/rewards');
    } catch (err) {
      setError(explain(err));
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    setError(null);
    try {
      const r = await post<{ dev_codes: Record<string, string> | null }>('/auth/resend', { email: form.email });
      setResent(r.dev_codes?.email ?? '');
    } catch (err) {
      setError(explain(err));
    }
  };

  if (!registered)
    return (
      <Shell title="Create your TelcronID" sub="One verified identity signs everything you contribute.">
        <form onSubmit={register} className="space-y-5">
          <Field label="Name" required minLength={2} maxLength={80} autoComplete="name" value={form.display_name} onChange={set('display_name')} />
          <Field label="Email" type="email" required autoComplete="email" value={form.email} onChange={set('email')} />
          <Field label="Mobile number (optional)" type="tel" pattern="\+[1-9]( ?[0-9]){7,14}" placeholder="+1 555 010 0123" hint="With country code. Not verified yet; phone checks come later." autoComplete="tel" value={form.phone_e164} onChange={set('phone_e164')} />
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
    // The answer to /auth/register is the same for a new address and a taken one (DEF-043): a new
    // address gets a code, an existing account's owner gets a notice to sign in instead.
    <Shell title="Check your email" sub={`We sent an email to ${form.email}. Enter the six-digit code in it to reach Level 1 and earn 100 TelCoins. If it says you already have an account, sign in instead.`}>
      <form onSubmit={verify} className="space-y-5" aria-label="Confirm your email">
        {registered.dev_codes?.email && (
          <Notice>Development build: your code is {registered.dev_codes.email}.</Notice>
        )}
        {!registered.email_sent && !registered.dev_codes?.email && (
          <Notice tone="error">We could not send the email just now. Wait a minute and use “Send a new code” below. If it still does not arrive, write to info@telcron.net.</Notice>
        )}
        <Field label="Code from the email" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required value={code} onChange={(e) => setCode(e.target.value)} />
        {error && <Notice tone="error">{error}</Notice>}
        {resent !== null && <Notice tone="ok">If that address has an account waiting, a new code is on its way{resent ? ` (development build: ${resent})` : ''}. Check your spam folder too.</Notice>}
        <button className="btn w-full !py-3.5" disabled={busy}>{busy ? 'Checking…' : 'Confirm and continue'}</button>
        <p className="text-center text-sm text-muted">No email? <button type="button" className="font-semibold text-action" onClick={resend}>Send a new code</button> (once a minute)</p>
        <p className="text-center text-sm text-muted">Already have an account? <Link className="font-semibold text-action" to="/sign-in">Sign in</Link></p>
      </form>
    </Shell>
  );
}
