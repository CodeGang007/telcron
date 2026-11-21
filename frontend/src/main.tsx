import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import './index.css';
import { AuthProvider } from './lib/auth';
import { SignIn, SignUp } from './pages/Auth';
import { Home } from './pages/Home';
import { NotFound } from './pages/NotFound';
import { Product } from './pages/Product';
import { Search } from './pages/Search';

const Scan = lazy(() => import('./pages/Scan').then((m) => ({ default: m.Scan })));
const Report = lazy(() => import('./pages/Report').then((m) => ({ default: m.Report })));
const Rewards = lazy(() => import('./pages/Rewards').then((m) => ({ default: m.Rewards })));
const Leaderboard = lazy(() => import('./pages/Leaderboard').then((m) => ({ default: m.Leaderboard })));
const ReviewQueue = lazy(() => import('./pages/ReviewQueue').then((m) => ({ default: m.ReviewQueue })));
const DataSources = lazy(() => import('./pages/DataSources').then((m) => ({ default: m.DataSources })));
const Wallet = lazy(() => import('./pages/Wallet').then((m) => ({ default: m.Wallet })));
const AdminLayout = lazy(() => import('./pages/admin/AdminLayout').then((m) => ({ default: m.AdminLayout })));
const AdminHome = lazy(() => import('./pages/admin/AdminHome').then((m) => ({ default: m.AdminHome })));
const Recalls = lazy(() => import('./pages/Recalls').then((m) => ({ default: m.Recalls })));

// After a deploy, an open tab asks for page files that no longer exist: reload once to get the new
// version instead of showing nothing.
window.addEventListener('vite:preloadError', () => {
  try {
    if (sessionStorage.getItem('telcron-reloaded')) return;
    sessionStorage.setItem('telcron-reloaded', '1');
  } catch { /* storage blocked: still reload */ }
  window.location.reload();
});
window.addEventListener('load', () => { try { sessionStorage.removeItem('telcron-reloaded'); } catch { /* ignore */ } });

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="search" element={<Search />} />
            <Route path="scan" element={<Scan />} />
            <Route path="products/:slug" element={<Product />} />
            <Route path="products/:slug/report" element={<Report />} />
            <Route path="sign-in" element={<SignIn />} />
            <Route path="sign-up" element={<SignUp />} />
            <Route path="verify" element={<SignUp />} />
            <Route path="wallet" element={<Wallet />} />
            <Route path="rewards" element={<Rewards />} />
            <Route path="leaderboard" element={<Leaderboard />} />
            <Route path="review-queue" element={<Navigate to="/admin/review-queue" replace />} />
            <Route path="recalls" element={<Recalls />} />
            <Route path="data-sources" element={<Navigate to="/admin/data-sources" replace />} />
            <Route path="admin" element={<AdminLayout />}>
              <Route index element={<AdminHome />} />
              <Route path="data-sources" element={<DataSources />} />
              <Route path="review-queue" element={<ReviewQueue />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
