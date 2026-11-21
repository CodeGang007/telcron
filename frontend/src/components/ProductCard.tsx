import { ArrowUpRight } from 'lucide-react';
import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { apiUrl, type ProductSummary } from '../lib/api';
import { CategoryTile, StatusBadge, scoreTone, stagger } from './ui';

export function ProductCard({ product }: { product: ProductSummary }) {
  const score = product.trust_score;
  return (
    <motion.div variants={stagger.item}>
      <Link to={`/products/${product.slug}`} className="card card-hover group flex h-full flex-col">
        <div className="flex items-start justify-between gap-3">
          {product.image_url ? (
            <img src={apiUrl(product.image_url)} alt="" loading="lazy" className="size-12 rounded-2xl border border-line object-cover" />
          ) : (
            <CategoryTile category={product.category} />
          )}
          <StatusBadge badge={product.status_badge} />
        </div>
        <p className="eyebrow mt-5">{product.category}</p>
        <h3 className="mt-1.5 font-display text-lg font-bold leading-snug group-hover:text-brand-ink">{product.name}</h3>
        <p className="mt-1 text-sm text-muted">{[product.brand, product.model_number].filter(Boolean).join(' · ')}</p>
        <div className="mt-auto flex items-end justify-between pt-6">
          {score !== null ? (
            <div>
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted">Trust score</p>
              <div className="mt-1.5 flex items-center gap-3">
                <span className="font-display text-2xl font-extrabold" style={{ color: scoreTone(score) }}>{Math.round(score)}</span>
                <span className="h-1.5 w-24 overflow-hidden rounded-full bg-neutral-tint">
                  <span className="block h-full rounded-full" style={{ width: `${score}%`, background: scoreTone(score) }} />
                </span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted">Not enough information yet</p>
          )}
          <span className="grid size-9 place-items-center rounded-full bg-panel text-muted transition group-hover:bg-brand-ink group-hover:text-white">
            <ArrowUpRight className="size-4" />
          </span>
        </div>
      </Link>
    </motion.div>
  );
}
