import { Printer } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { LogoMark } from '../components/Logo';
import { Skeleton } from '../components/ui';
import { api, type Passport, type ProductDetail } from '../lib/api';
import { useLoad } from '../lib/useLoad';

/** The full hazard report: the passport with every score and every piece of evidence, ready to print
    or save as PDF from the browser. */
export function Report() {
  const { slug = '' } = useParams();
  const product = useLoad(() => api<ProductDetail>(`/products/${slug}`), [slug]);
  const passport = useLoad(() => api<Passport>(`/products/${slug}/passport`), [slug]);
  if (product.loading || passport.loading) return <div className="container-page py-12"><Skeleton className="h-96 w-full" /></div>;
  const p = product.data;
  const pass = passport.data;
  if (!p || !pass) return <div className="container-page py-12 text-muted">This product has no passport yet.</div>;
  return (
    <div className="container-page max-w-3xl py-12 print:max-w-none print:py-0">
      <div className="mb-8 flex items-center justify-between print:hidden">
        <p className="text-sm text-muted">Use your browser&apos;s print dialog to save this as a PDF.</p>
        <button className="btn" onClick={() => window.print()}><Printer className="size-4" />Print or save as PDF</button>
      </div>
      <article className="rounded-3xl border border-line bg-white p-10 print:border-0 print:p-0">
        <header className="flex items-start justify-between border-b border-line pb-6">
          <div>
            <p className="eyebrow">Telcron hazard report</p>
            <h1 className="mt-2 font-display text-3xl font-extrabold">{p.name}</h1>
            <p className="mt-1 text-muted">{[p.brand, p.model_number, p.category].filter(Boolean).join(' · ')}</p>
          </div>
          <LogoMark size={44} />
        </header>
        <dl className="mt-6 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div><dt className="text-muted">Status</dt><dd className="font-semibold capitalize">{pass.status_badge.replace('_', ' ')}</dd></div>
          <div><dt className="text-muted">Trust score</dt><dd className="font-semibold">{pass.trust_score === null ? '—' : Math.round(pass.trust_score)} / 100</dd></div>
          <div><dt className="text-muted">Passport</dt><dd className="font-semibold">Version {pass.version}</dd></div>
          <div><dt className="text-muted">Issued</dt><dd className="font-semibold">{new Date(pass.verified_at).toLocaleDateString()}</dd></div>
        </dl>
        {pass.recall_matches.length > 0 && (
          <section className="mt-8">
            <h2 className="font-display text-lg font-bold">Recalls</h2>
            {pass.recall_matches.map((r) => (
              <div key={r.recall_id} className="mt-3 rounded-xl border border-danger/30 p-4 text-sm">
                <p className="font-semibold">{r.title}</p>
                {r.hazard && <p className="mt-1">{r.hazard}</p>}
                {r.remedy && <p className="mt-1 text-muted">What to do: {r.remedy}</p>}
                {r.url && <p className="mt-1 text-xs text-muted">{r.url}</p>}
              </div>
            ))}
          </section>
        )}
        {pass.hazard && (
          <section className="mt-8">
            <h2 className="font-display text-lg font-bold">Hazard assessment · {pass.hazard.label ?? 'not enough evidence'}</h2>
            <p className="text-xs text-muted">Scored by {pass.hazard.model_code}. Higher means more hazardous.</p>
            <table className="mt-3 w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase text-muted"><tr><th className="py-2">Dimension</th><th>Weight</th><th>Score</th><th>Evidence</th></tr></thead>
              <tbody className="divide-y divide-line align-top">
                {pass.hazard.dimensions.map((d) => (
                  <tr key={d.code}>
                    <td className="py-3 pr-3 font-medium">{d.name}<p className="text-xs font-normal text-muted">{d.justification}</p></td>
                    <td className="py-3 pr-3">{d.weight}</td>
                    <td className="py-3 pr-3 font-semibold">{d.score === null ? '—' : Math.round(d.score)}</td>
                    <td className="py-3 text-xs text-muted">{d.citations.map((c) => <p key={c.id} className="mb-1">[{c.kind}] {c.excerpt}</p>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
        {p.certifications.length > 0 && (
          <section className="mt-8">
            <h2 className="font-display text-lg font-bold">Certificates</h2>
            <ul className="mt-2 text-sm">{p.certifications.map((c) => <li key={c.scheme + c.identifier}>{c.scheme.toUpperCase()} {c.identifier}: {c.status.replace('_', ' ')}</li>)}</ul>
          </section>
        )}
        <footer className="mt-10 border-t border-line pt-4 text-xs text-muted">Generated {new Date().toLocaleString()} from Telcron passport version {pass.version}. Recall data: US Consumer Product Safety Commission.</footer>
      </article>
    </div>
  );
}
