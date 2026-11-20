import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import './index.css';
import { AuthProvider } from './lib/auth';
import { SignIn, SignUp } from './pages/Auth';
import { Home } from './pages/Home';
import { Product } from './pages/Product';
import { Search } from './pages/Search';

const Scan = lazy(() => import('./pages/Scan').then((m) => ({ default: m.Scan })));
const Report = lazy(() => import('./pages/Report').then((m) => ({ default: m.Report })));
const Rewards = lazy(() => import('./pages/Rewards').then((m) => ({ default: m.Rewards })));
const Leaderboard = lazy(() => import('./pages/Leaderboard').then((m) => ({ default: m.Leaderboard })));
const ReviewQueue = lazy(() => import('./pages/ReviewQueue').then((m) => ({ default: m.ReviewQueue })));
const DataSources = lazy(() => import('./pages/DataSources').then((m) => ({ default: m.DataSources })));
const Wallet = lazy(() => import('./pages/Wallet').then((m) => ({ default: m.Wallet })));
const Recalls = lazy(() => import('./pages/Recalls').then((m) => ({ default: m.Recalls })));

function NotFound() {
  return <div className="container-page py-24 text-center text-muted">That page does not exist.</div>;
}

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
            <Route path="review-queue" element={<ReviewQueue />} />
            <Route path="recalls" element={<Recalls />} />
            <Route path="data-sources" element={<DataSources />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
