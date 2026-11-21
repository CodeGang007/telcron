import { Search, ScanLine } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';

export function SearchBox({ initial = '', autoFocus = false, dark = false }: { initial?: string; autoFocus?: boolean; dark?: boolean }) {
  const [q, setQ] = useState(initial);
  const navigate = useNavigate();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    navigate(`/search?q=${encodeURIComponent(q.trim())}`);
  };
  return (
    <form
      onSubmit={submit}
      role="search"
      className={`group flex w-full max-w-2xl items-center gap-2 rounded-2xl p-1.5 transition ${
        dark ? 'bg-white shadow-float' : 'border border-line bg-white shadow-soft focus-within:border-action focus-within:ring-4 focus-within:ring-action/10'
      }`}
    >
      <Search className="ml-3 size-5 shrink-0 text-muted" />
      <label className="sr-only" htmlFor="product-search">Search by product name, brand or barcode</label>
      <input
        id="product-search"
        className="min-w-0 flex-1 bg-transparent px-1 py-2.5 text-sm text-ink outline-none placeholder:text-muted/70"
        placeholder="Search by product name, brand or barcode"
        value={q}
        autoFocus={autoFocus}
        onChange={(e) => setQ(e.target.value)}
      />
      <Link to="/scan" className="hidden rounded-xl p-2.5 text-muted transition hover:bg-panel hover:text-brand-ink sm:block" aria-label="Scan a barcode instead">
        <ScanLine className="size-5" />
      </Link>
      <button className="btn !rounded-xl !px-5">Search</button>
    </form>
  );
}
