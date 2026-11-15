import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

export function SearchBox({ initial = '', autoFocus = false }: { initial?: string; autoFocus?: boolean }) {
  const [q, setQ] = useState(initial);
  const navigate = useNavigate();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    navigate(`/search?q=${encodeURIComponent(q.trim())}`);
  };
  return (
    <form onSubmit={submit} role="search" className="flex w-full max-w-2xl gap-2">
      <label className="sr-only" htmlFor="product-search">
        Search by product name, brand or barcode
      </label>
      <input
        id="product-search"
        className="field !rounded-lg italic placeholder:text-muted"
        placeholder="Search by product name, brand or barcode"
        value={q}
        autoFocus={autoFocus}
        onChange={(e) => setQ(e.target.value)}
      />
      <button className="btn shrink-0">Search</button>
    </form>
  );
}
