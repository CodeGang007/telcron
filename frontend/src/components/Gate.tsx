import { LockKeyhole, MailCheck, RefreshCw, WifiOff } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { EmptyState, Skeleton } from './ui';

/** A stored session that could not be checked because Telcron was unreachable: the member is still
    signed in, so offer a retry, never a sign-in form that cannot reach Telcron either (DEF-100). */
function Unreachable({ message, reload }: { message: string; reload: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const retry = async () => {
    setBusy(true);
    try {
      await reload();
    } finally {
      setBusy(false);
    }
  };
  return (
    <div role="alert">
      <EmptyState
        icon={WifiOff}
        title="Could not reach Telcron"
        action={
          <button className="btn min-h-11" disabled={busy} onClick={() => void retry()}>
            <RefreshCw className={`size-4 ${busy ? 'animate-spin' : ''}`} />Try again
          </button>
        }
      >
        {message} You are still signed in.
      </EmptyState>
    </div>
  );
}

/** A members-only page body: signed out, or not yet Level 1, gets a way forward, not an error. */
export function Gate({ children }: { children: ReactNode }) {
  const { me, loading, unreachable, reload } = useAuth();
  if (loading) return <Skeleton className="h-64 w-full rounded-3xl" />;
  if (!me && unreachable) return <Unreachable message={unreachable} reload={reload} />;
  if (!me)
    return (
      <EmptyState
        icon={LockKeyhole}
        title="Sign in to continue"
        action={
          <div className="flex gap-3">
            <Link to="/sign-in" className="btn">Sign in</Link>
            <Link to="/sign-up" className="btn-ghost">Create account</Link>
          </div>
        }
      >
        This page is part of your TelcronID.
      </EmptyState>
    );
  if (me.verification_level < 1)
    return (
      <EmptyState icon={MailCheck} title="Confirm your email first">
        Enter the six-digit code we emailed you. Verified members can save products, contribute and earn TelCoins.
      </EmptyState>
    );
  return <>{children}</>;
}
