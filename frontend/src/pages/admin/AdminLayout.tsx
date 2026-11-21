import { LockKeyhole } from 'lucide-react';
import { Suspense } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { EmptyState, Skeleton } from '../../components/ui';
import { useAuth } from '../../lib/auth';
import { NotFound } from '../NotFound';
import { SECTIONS, isStaff, sectionsFor } from './sections';

const trim = (path: string) => path.replace(/\/+$/, '') || '/';

/**
 * The staff-only area (WO-055). A visitor is offered sign-in; a signed-in member who is not staff, or a
 * moderator on an admin-only section, gets the ordinary not-found page so the area is never revealed.
 */
export function AdminLayout() {
  const { me, loading } = useAuth();
  const { pathname } = useLocation();

  if (loading)
    return (
      <div className="container-page py-12" role="status" aria-label="Loading">
        <Skeleton className="h-72 w-full rounded-3xl" />
      </div>
    );
  if (!me)
    return (
      <div className="container-page py-12">
        <EmptyState
          icon={LockKeyhole}
          title="Sign in to continue"
          action={<Link to="/sign-in" className="btn">Sign in</Link>}
        >
          This page needs a signed-in account.
        </EmptyState>
      </div>
    );
  if (!isStaff(me.role)) return <NotFound />;

  const mine = sectionsFor(me.role);
  const current = SECTIONS.find((s) => s.to === trim(pathname));
  if (current && !mine.includes(current)) return <NotFound />;

  const link = ({ isActive }: { isActive: boolean }) =>
    `flex shrink-0 items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium transition lg:rounded-xl ${
      isActive ? 'bg-brand-tint text-brand-ink' : 'text-muted hover:bg-panel hover:text-ink'
    }`;

  return (
    <div className="container-page pt-6 lg:flex lg:gap-10 lg:pt-12">
      <nav aria-label="Admin sections" className="lg:w-56 lg:shrink-0">
        <p className="eyebrow mb-3 hidden lg:block">Admin</p>
        <ul className="-mx-4 flex gap-2 overflow-x-auto border-b border-line px-4 pb-3 sm:-mx-6 sm:px-6 lg:mx-0 lg:flex-col lg:gap-1 lg:overflow-visible lg:border-0 lg:px-0 lg:pb-0">
          {mine.map((s) => (
            <li key={s.to}>
              <NavLink to={s.to} end className={link}>
                <s.icon className="size-4" aria-hidden />
                {s.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      {/* The section pages are full pages with their own container: inside the shell they take its width. */}
      <div className="min-w-0 flex-1 [&>.container-page]:max-w-none [&>.container-page]:px-0 [&>.container-page]:pt-6 lg:[&>.container-page]:pt-0">
        <Suspense fallback={<Skeleton className="mt-6 h-72 w-full rounded-3xl lg:mt-0" />}>
          <Outlet />
        </Suspense>
      </div>
    </div>
  );
}
