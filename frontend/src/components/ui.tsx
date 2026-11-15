import type { ReactNode } from 'react';

const BADGES: Record<string, { label: string; cls: string }> = {
  verified: { label: 'Verified', cls: 'bg-ok-tint text-ok' },
  caution: { label: 'Caution', cls: 'bg-warn-tint text-warn' },
  recalled: { label: 'Recalled', cls: 'bg-danger-tint text-danger' },
  blocked: { label: 'Blocked', cls: 'bg-danger-tint text-danger' },
  unverified: { label: 'Not yet verified', cls: 'bg-neutral-tint text-muted' },
};

export function StatusBadge({ badge }: { badge: string | null }) {
  const b = BADGES[badge ?? ''] ?? { label: 'Not screened', cls: 'bg-neutral-tint text-muted' };
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${b.cls}`}>
      {b.label}
    </span>
  );
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'error' | 'ok'; children: ReactNode }) {
  const cls = {
    info: 'bg-panel text-muted',
    error: 'bg-danger-tint text-danger',
    ok: 'bg-ok-tint text-ok',
  }[tone];
  return (
    <p role={tone === 'error' ? 'alert' : 'status'} className={`rounded-2xl px-4 py-3 text-sm ${cls}`}>
      {children}
    </p>
  );
}

export function Stars({ rating }: { rating: number }) {
  return (
    <span aria-label={`${rating} out of 5`} className="text-warn">
      {'★'.repeat(rating)}
      <span className="text-line">{'★'.repeat(5 - rating)}</span>
    </span>
  );
}

export function PageTitle({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <header className="mb-8">
      {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
      <h1 className="text-3xl font-semibold sm:text-4xl">{title}</h1>
      {children && <p className="mt-3 max-w-2xl text-muted">{children}</p>}
    </header>
  );
}
