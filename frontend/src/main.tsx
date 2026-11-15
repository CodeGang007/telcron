import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import './index.css';
import { AuthProvider } from './lib/auth';
import { SignIn, SignUp } from './pages/Auth';
import { Home } from './pages/Home';
import { Leaderboard, Rewards, Wallet } from './pages/Member';
import { Product } from './pages/Product';
import { Search } from './pages/Search';

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
            <Route path="products/:slug" element={<Product />} />
            <Route path="sign-in" element={<SignIn />} />
            <Route path="sign-up" element={<SignUp />} />
            <Route path="verify" element={<SignUp />} />
            <Route path="wallet" element={<Wallet />} />
            <Route path="rewards" element={<Rewards />} />
            <Route path="leaderboard" element={<Leaderboard />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
