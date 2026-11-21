import {
  ChevronDown,
  ClipboardCheck,
  Coins,
  Database,
  Home,
  LogOut,
  Megaphone,
  ScanLine,
  Search,
  Trophy,
  Wallet,
  type LucideIcon,
} from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { Suspense, useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { ErrorBoundary } from './ErrorBoundary';
import { Logo, LogoMark } from './Logo';

type Item = { to: string; label: string; icon: LucideIcon };
const NAV: Item[] = [
  { to: '/search', label: 'Products', icon: Search },
  { to: '/recalls', label: 'Recalls', icon: Megaphone },
  { to: '/wallet', label: 'Wallet', icon: Wallet },
  { to: '/rewards', label: 'Rewards', icon: Coins },
  { to: '/leaderboard', label: 'Leaderboard', icon: Trophy },
];

function initials(name: string) {
  return name.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();
}

function UserMenu() {
  const { me, signOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [coins, setCoins] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const location = useLocation();

  useEffect(() => {
    if (!me || me.verification_level < 1) return;
    api<{ confirmed: number }>('/coins').then((c) => setCoins(c.confirmed)).catch(() => setCoins(null));
  }, [me, location.pathname]);
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);
  if (!me) return null;
  const staff = me.role === 'admin' || me.role === 'moderator';
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 rounded-full border border-line bg-white py-1 pl-1 pr-3 transition hover:shadow-soft" aria-expanded={open} aria-haspopup="menu">
        <span className="grid size-8 place-items-center rounded-full bg-gradient-to-br from-brand-bright to-brand-deep text-xs font-bold text-white">{initials(me.display_name)}</span>
        {coins !== null && (
          <span className="chip bg-gold-tint !px-2 !py-0.5 text-gold" title="Confirmed TelCoins">
            <Coins className="size-3.5" />{coins.toLocaleString()}
          </span>
        )}
        <ChevronDown className={`size-4 text-muted transition ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.16 }}
            className="absolute right-0 top-12 z-40 w-64 origin-top-right rounded-2xl border border-line bg-white p-2 shadow-lift"
          >
            <div className="px-3 py-2">
              <p className="font-semibold">{me.display_name}</p>
              <p className="truncate text-xs text-muted">{me.email}</p>
              <p className="mt-1 text-xs text-muted">Level {me.verification_level} · trust {Math.round(me.trust_score)}</p>
            </div>
            <div className="my-1 h-px bg-line" />
            {[
              { to: '/wallet', label: 'Digital Wallet', icon: Wallet },
              { to: '/rewards', label: 'TelCoins & badges', icon: Coins },
              ...(staff ? [{ to: '/review-queue', label: 'Review queue', icon: ClipboardCheck }] : []),
              ...(me.role === 'admin' ? [{ to: '/data-sources', label: 'Data sources', icon: Database }] : []),
            ].map((i) => (
              <Link key={i.to} to={i.to} role="menuitem" className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition hover:bg-panel">
                <i.icon className="size-4 text-muted" />{i.label}
              </Link>
            ))}
            <div className="my-1 h-px bg-line" />
            <button
              role="menuitem"
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-danger transition hover:bg-danger-tint"
              onClick={async () => { await signOut(); navigate('/'); }}
            >
              <LogOut className="size-4" />Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function TabBar() {
  const tabs: Item[] = [
    { to: '/', label: 'Home', icon: Home },
    { to: '/search', label: 'Search', icon: Search },
    { to: '/scan', label: 'Scan', icon: ScanLine },
    { to: '/wallet', label: 'Wallet', icon: Wallet },
    { to: '/rewards', label: 'Rewards', icon: Coins },
  ];
  return (
    <nav aria-label="Tabs" className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden">
      <ul className="mx-auto grid max-w-md grid-cols-5">
        {tabs.map((t) => (
          <li key={t.to}>
            <NavLink to={t.to} end={t.to === '/'} className={({ isActive }) => `flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium ${isActive ? 'text-brand-ink' : 'text-muted'}`}>
              {t.to === '/scan' ? (
                <span className="-mt-6 grid size-14 place-items-center rounded-full bg-gradient-to-br from-brand-bright to-brand-deep text-white shadow-[0_10px_24px_-8px_rgb(226_55_68/0.8)] ring-4 ring-white">
                  <t.icon className="size-6" />
                </span>
              ) : (
                <t.icon className="size-5" />
              )}
              {t.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function Layout() {
  const { me } = useAuth();
  const location = useLocation();
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  // Braces matter: newer Chrome returns a promise from scrollTo, which React would take for a cleanup.
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);
  const dark = location.pathname === '/' && !scrolled;

  return (
    <div className="flex min-h-screen flex-col">
      <header className={`fixed inset-x-0 top-0 z-30 transition duration-300 ${dark ? 'bg-transparent' : 'border-b border-line/80 bg-white/80 shadow-[0_1px_0_rgb(15_23_42/0.02)] backdrop-blur-xl'}`}>
        <div className="container-page flex h-16 items-center justify-between gap-6">
          <Logo dark={dark} />
          <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) =>
                  `relative flex items-center gap-2 rounded-full px-3.5 py-2 text-sm font-medium transition ${
                    dark ? (isActive ? 'text-white' : 'text-white/70 hover:text-white') : isActive ? 'text-ink' : 'text-muted hover:text-ink'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && <motion.span layoutId="nav-pill" className={`absolute inset-0 rounded-full ${dark ? 'bg-white/10' : 'bg-panel'}`} transition={{ type: 'spring', bounce: 0.2, duration: 0.5 }} />}
                    <n.icon className="relative size-4" />
                    <span className="relative">{n.label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/scan" className={`hidden items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition sm:flex ${dark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-brand-tint text-brand-ink hover:bg-brand-ink hover:text-white'}`}>
              <ScanLine className="size-4" />Scan
            </Link>
            {me ? <UserMenu /> : <Link to="/sign-in" className="btn btn-sm">Sign in</Link>}
          </div>
        </div>
      </header>

      <main className={`flex-1 pb-24 lg:pb-0 ${location.pathname === '/' ? '' : 'pt-16'}`}>
        <AnimatePresence mode="wait">
          <motion.div key={location.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.22, ease: 'easeOut' }}>
            <Suspense fallback={<div className="container-page py-12"><div className="skeleton h-72 w-full rounded-[2rem]" /></div>}>
              <ErrorBoundary key={location.pathname}><Outlet /></ErrorBoundary>
            </Suspense>
          </motion.div>
        </AnimatePresence>
      </main>

      <footer className="hidden border-t border-line bg-panel/60 lg:block">
        <div className="container-page grid gap-10 py-14 text-sm text-muted md:grid-cols-4">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2.5">
              <LogoMark size={30} />
              <span className="font-display text-lg font-extrabold text-ink">Telcron</span>
            </div>
            <p className="mt-4 max-w-sm">One permanent record per product, one verified identity per person, and a piece of evidence behind every safety claim.</p>
            <p className="mt-4">info@telcron.net</p>
          </div>
          <div>
            <p className="mb-3 font-semibold text-ink">Explore</p>
            <ul className="space-y-2">
              <li><Link className="hover:text-ink" to="/search">Search products</Link></li>
              <li><Link className="hover:text-ink" to="/scan">Scan a barcode</Link></li>
              <li><Link className="hover:text-ink" to="/recalls">Recall notices</Link></li>
            </ul>
          </div>
          <div>
            <p className="mb-3 font-semibold text-ink">Members</p>
            <ul className="space-y-2">
              <li><Link className="hover:text-ink" to="/wallet">Digital Wallet</Link></li>
              <li><Link className="hover:text-ink" to="/rewards">TelCoins</Link></li>
              <li><Link className="hover:text-ink" to="/leaderboard">Leaderboard</Link></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-line py-5 text-center text-xs text-muted">Recall data: US Consumer Product Safety Commission. Product data: UPCitemdb.</div>
      </footer>

      <TabBar />
      <Toaster position="top-center" richColors closeButton toastOptions={{ className: 'font-sans' }} />
    </div>
  );
}
