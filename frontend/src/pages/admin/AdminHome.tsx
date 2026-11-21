import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageTitle } from '../../components/ui';
import { useAuth } from '../../lib/auth';
import { sectionsFor } from './sections';

/** The admin overview: one card per section the caller can open. No figures until an API serves them. */
export function AdminHome() {
  const { me } = useAuth();
  const sections = sectionsFor(me?.role).filter((s) => s.to !== '/admin');
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow={me?.role === 'admin' ? 'Admin' : 'Safety team'} title="Overview">
        Pick a section to work in.
      </PageTitle>
      <ul className="grid gap-4 sm:grid-cols-2">
        {sections.map((s) => (
          <li key={s.to}>
            <Link to={s.to} className="card group flex h-full items-start gap-4 transition hover:shadow-lift">
              <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-brand-tint text-brand-ink">
                <s.icon className="size-6" aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2 font-display text-lg font-bold">
                  {s.label}
                  <ArrowRight className="size-4 text-muted transition group-hover:translate-x-0.5" aria-hidden />
                </span>
                <span className="mt-1 block text-sm text-muted">{s.blurb}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
