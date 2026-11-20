import { LockKeyhole, MailCheck } from 'lucide-react';
import { type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { EmptyState, Skeleton } from './ui';

/** A members-only page body: signed out, or not yet Level 1, gets a way forward, not an error. */
export function Gate({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <Skeleton className="h-64 w-full rounded-3xl" />;
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
      <EmptyState icon={MailCheck} title="Confirm your email and phone first">
        Verified members can save products, contribute and earn TelCoins.
      </EmptyState>
    );
  return <>{children}</>;
}
