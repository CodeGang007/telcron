import { PackagePlus, PackageSearch, ScanLine, Search as SearchIcon } from 'lucide-react';
import { motion } from 'motion/react';
import { Link, useSearchParams } from 'react-router-dom';
import { ProductCard } from '../components/ProductCard';
import { SearchBox } from '../components/SearchBox';
import { CardSkeletons, EmptyState, Notice, PageTitle, Pager, stagger } from '../components/ui';
import type { ProductSummary } from '../lib/api';
import { usePaged } from '../lib/usePaged';

export function Search() {
  const [params] = useSearchParams();
  const q = params.get('q') ?? '';
  const results = usePaged<ProductSummary>(`/products?q=${encodeURIComponent(q)}`, 12);
  return (
    <div className="container-page py-12">
      <PageTitle eyebrow="Products" title={q ? `Results for “${q}”` : 'Every product in the registry'} icon={SearchIcon} />
      <SearchBox key={q} initial={q} />
      <div className="mt-10">
        {results.loading && <CardSkeletons />}
        {results.error && (
          <Notice tone="error">{results.error} <button className="font-semibold underline" onClick={() => void results.reload()}>Try again</button></Notice>
        )}
        {/* "No product matches" only when the search answered with nothing; a failed request is not an answer (DEF-036). */}
        {!results.loading && !results.error && results.items.length === 0 && (
          <EmptyState
            icon={PackageSearch}
            title={`No product matches “${q}”`}
            action={<Link to="/scan" className="btn"><ScanLine className="size-4" />Scan its barcode instead</Link>}
          >
            Check the spelling, or try the brand or the barcode. Scanning a barcode adds a product we have not seen before.
          </EmptyState>
        )}
        {!results.loading && results.items.length > 0 && (
          <motion.div key={q} variants={stagger.container} initial="hidden" animate="show" className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {results.items.map((p) => <ProductCard key={p.id} product={p} />)}
          </motion.div>
        )}
        <Pager hasMore={results.hasMore} loading={results.loadingMore} onMore={results.more} shown={results.items.length} />
        {q && !results.loading && !results.hasMore && results.items.length > 0 && (
          <div className="mt-8 flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-dashed border-line bg-panel/60 px-6 py-5">
            <p className="text-sm"><span className="font-semibold">Not the one you meant?</span> <span className="text-muted">Scan its barcode or photograph it: we add it, research it and issue its passport.</span></p>
            <Link to="/scan" className="btn btn-sm"><PackagePlus className="size-4" />Add a product</Link>
          </div>
        )}
      </div>
    </div>
  );
}
