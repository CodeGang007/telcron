import { useSearchParams } from 'react-router-dom';
import { ProductCard } from '../components/ProductCard';
import { SearchBox } from '../components/SearchBox';
import { Notice, PageTitle } from '../components/ui';
import { api, type ProductSummary } from '../lib/api';
import { useLoad } from '../lib/useLoad';

export function Search() {
  const [params] = useSearchParams();
  const q = params.get('q') ?? '';
  const { data, error, loading } = useLoad(
    () => api<ProductSummary[]>(`/products?q=${encodeURIComponent(q)}`),
    [q],
  );
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Products" title={q ? `Results for “${q}”` : 'All products'} />
      <SearchBox key={q} initial={q} />
      <div className="mt-10">
        {loading && <Notice>Searching…</Notice>}
        {error && <Notice tone="error">{error}</Notice>}
        {data && data.length === 0 && (
          <Notice>No product matches “{q}”. Check the spelling, or try the brand or the barcode.</Notice>
        )}
        {data && data.length > 0 && (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {data.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
