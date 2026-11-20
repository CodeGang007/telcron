import { Link } from 'react-router-dom';

/** Telcron's mark: a shield holding a check, cut with a scan line. */
export function LogoMark({ size = 36, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden className={className}>
      <defs>
        <linearGradient id="tc-shield" x1="6" y1="3" x2="34" y2="37" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--color-brand-bright)" />
          <stop offset="1" stopColor="var(--color-brand-deep)" />
        </linearGradient>
      </defs>
      <path d="M20 3 34 8.5v10.2c0 8.6-5.8 15.6-14 18.3C11.8 34.3 6 27.3 6 18.7V8.5L20 3Z" fill="url(#tc-shield)" />
      <path d="M13.5 19.5 18 24l9-9.5" stroke="white" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="9" y="28.6" width="22" height="1.6" rx="0.8" fill="white" opacity="0.35" />
    </svg>
  );
}

export function Logo({ dark = false }: { dark?: boolean }) {
  return (
    <Link to="/" className="group flex items-center gap-2.5" aria-label="Telcron home">
      <LogoMark className="transition duration-300 group-hover:rotate-[-6deg] group-hover:scale-105" />
      <span className="flex flex-col leading-none">
        <span className={`font-display text-xl font-extrabold tracking-tight ${dark ? 'text-white' : 'text-ink'}`}>
          Telcron
        </span>
        <span className={`mt-0.5 text-[10px] font-medium ${dark ? 'text-white/60' : 'text-muted'}`}>
          Product safety, verified
        </span>
      </span>
    </Link>
  );
}
