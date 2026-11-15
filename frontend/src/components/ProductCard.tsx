import { Link } from 'react-router-dom';
import type { ProductSummary } from '../lib/api';
import { StatusBadge } from './ui';

export function ProductCard({ product }: { product: ProductSummary }) {
  return (
    <Link to={`/products/${product.slug}`} className="card block transition hover:border-action">
      <div className="flex items-start justify-between gap-3">
        <p className="eyebrow">{product.category}</p>
        <StatusBadge badge={product.status_badge} />
      </div>
      <h3 className="mt-3 text-lg font-semibold">{product.name}</h3>
      <p className="mt-1 text-sm text-muted">
        {[product.brand, product.model_number].filter(Boolean).join(' · ')}
      </p>
      {product.trust_score !== null && (
        <p className="mt-4 text-sm text-muted">
          Trust score <span className="font-semibold text-ink">{Math.round(product.trust_score)}</span> / 100
        </p>
      )}
    </Link>
  );
}
