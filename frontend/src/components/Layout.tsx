import { useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';

const NAV = [
  { to: '/search', label: 'Products' },
  { to: '/wallet', label: 'Digital Wallet' },
  { to: '/rewards', label: 'Telcron Rewards' },
  { to: '/leaderboard', label: 'Leaderboard' },
];

function Wordmark() {
  return (
    <Link to="/" className="flex flex-col leading-none" aria-label="Telcron home">
      <span className="text-2xl font-bold tracking-tight text-brand-ink">TELCRON</span>
      <span className="text-[10px] text-muted">A smarter way to product safety</span>
    </Link>
  );
}

export function Layout() {
  const { me, signOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const link = ({ isActive }: { isActive: boolean }) =>
    `text-sm uppercase tracking-wide transition hover:text-brand-ink ${isActive ? 'text-brand-ink' : 'text-muted'}`;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-white">
        <div className="container-page flex h-20 items-center justify-between gap-6">
          <Wordmark />
          <nav aria-label="Main" className="hidden items-center gap-8 md:flex">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} className={link}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            {me ? (
              <>
                <span className="hidden text-sm text-muted sm:inline">{me.display_name}</span>
                <button
                  className="btn-ghost !px-4 !py-2"
                  onClick={async () => {
                    await signOut();
                    navigate('/');
                  }}
                >
                  Sign out
                </button>
              </>
            ) : (
              <Link to="/sign-in" className="btn">
                Sign In
              </Link>
            )}
            <button
              className="rounded-lg p-2 text-muted md:hidden"
              aria-label="Menu"
              aria-expanded={open}
              onClick={() => setOpen(!open)}
            >
              ☰
            </button>
          </div>
        </div>
        {open && (
          <nav aria-label="Mobile" className="container-page flex flex-col gap-4 border-t border-line py-4 md:hidden">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} className={link} onClick={() => setOpen(false)}>
                {n.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-line">
        <div className="container-page grid gap-8 py-12 text-sm text-muted sm:grid-cols-3">
          <div>
            <Wordmark />
            <p className="mt-4">info@telcron.net</p>
          </div>
          <div>
            <p className="mb-3 font-semibold text-ink">Products</p>
            <ul className="space-y-2">
              <li><Link to="/search">Search products</Link></li>
              <li><Link to="/wallet">Digital Wallet</Link></li>
            </ul>
          </div>
          <div>
            <p className="mb-3 font-semibold text-ink">Rewards</p>
            <ul className="space-y-2">
              <li><Link to="/rewards">TelCoins</Link></li>
              <li><Link to="/leaderboard">Leaderboard</Link></li>
            </ul>
          </div>
        </div>
      </footer>
    </div>
  );
}
