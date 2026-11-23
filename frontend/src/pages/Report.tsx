import { AlertOctagon, LockKeyhole, Printer } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { LogoMark } from '../components/Logo';
import { RECALL_VERDICT, recallAsOf, shownRecalls } from '../components/Verdict';
import { EmptyState, Notice, Skeleton } from '../components/ui';
import { ApiError, api, type ProductReport } from '../lib/api';
import { useLoad } from '../lib/useLoad';

/** The store's price for the report (seeded `hazard_report_pdf`). The store itself shows the live price;
    this is only the unlock copy for someone who has not opened the store yet. */
const REPORT_COST = 50;

/** Who is asking, when the report is not theirs to read (CT-002): a visitor (401) or a member who has
    not redeemed it for this product (403 `report_not_redeemed`). */
type Locked = { locked: 'visitor' | 'member' };

async function loadReport(slug: string): Promise<ProductReport | Locked> {
  try {
    return await api<ProductReport>(`/products/${slug}/report`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return { locked: 'visitor' };
    if (e instanceof ApiError && e.status === 403 && e.code === 'report_not_redeemed') return { locked: 'member' };
    throw e;
  }
}

function Unlock({ slug, who }: { slug: string; who: Locked['locked'] }) {
  return (
    <div className="container-page py-16">
      <EmptyState
        icon={LockKeyhole}
        title={`Redeem for ${REPORT_COST} TelCoins to unlock`}
        action={
          <div className="flex flex-wrap justify-center gap-3">
            {who === 'visitor'
              ? <Link to="/sign-in" className="btn min-h-11">Sign in</Link>
              : <Link to={`/rewards?product=${encodeURIComponent(slug)}`} className="btn min-h-11">Open the coin store</Link>}
            <Link to={`/products/${slug}`} className="btn-ghost min-h-11">See the free passport</Link>
          </div>
        }
      >
        {who === 'visitor'
          ? 'The full hazard report, with every score and every piece of evidence, is for members who redeem it. Sign in, then redeem it in the coin store. The passport stays free for everyone.'
          : 'You have not unlocked the full report for this product yet. “Open the coin store” takes you to the store with this product already chosen: redeem it there with your confirmed TelCoins, then open the report from there or come back to this page. It does not need to be in your wallet. The passport stays free for everyone.'}
      </EmptyState>
    </div>
  );
}

/** The full hazard report: the passport with every score and every piece of evidence, ready to print
    or save as PDF from the browser. Only for the member who redeemed it for this product (DEF-035, CT-002);
    it never renders from the public reads. */
export function Report() {
  const { slug = '' } = useParams();
  const report = useLoad(() => loadReport(slug), [slug]);
  if (report.loading) return <div className="container-page py-12"><Skeleton className="h-96 w-full" /></div>;
  if (report.notFound)
    return (
      <div className="container-page py-16">
        <EmptyState icon={AlertOctagon} title="We could not find that product" action={<Link className="btn" to="/search">Search again</Link>} />
      </div>
    );
  if (report.error || !report.data)
    return (
      <div className="container-page py-12">
        <Notice tone="error">{report.error ?? 'Something went wrong. Try again.'} <button className="font-semibold underline" onClick={() => void report.reload()}>Try again</button></Notice>
      </div>
    );
  if ('locked' in report.data) return <Unlock slug={slug} who={report.data.locked} />;
  const { product: p, passport: pass } = report.data;
  if (!pass) return <div className="container-page py-12 text-muted">This product has no passport yet.</div>;
  const recalls = shownRecalls(pass);
  return (
    <div className="container-page max-w-3xl py-12 print:max-w-none print:py-0">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <p className="text-sm text-muted">Use your browser&apos;s print dialog to save this as a PDF.</p>
        <button className="btn" onClick={() => window.print()}><Printer className="size-4" />Print or save as PDF</button>
      </div>
      <article className="rounded-3xl border border-line bg-white p-5 sm:p-10 print:border-0 print:p-0">
        <header className="flex items-start justify-between gap-4 border-b border-line pb-6">
          <div className="min-w-0">
            <p className="eyebrow">Telcron hazard report</p>
            <h1 className="mt-2 break-words font-display text-2xl font-extrabold sm:text-3xl">{p.name}</h1>
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
        <section className="mt-8">
          <h2 className="font-display text-lg font-bold">Recalls</h2>
          {recalls.length === 0 && <p className="mt-2 text-sm text-muted">No recall notice matched it {recallAsOf(pass)}.</p>}
          {recalls.map((r) => (
            <div key={r.recall_id} className="mt-3 rounded-xl border border-danger/30 p-4 text-sm">
              <p className="text-xs font-bold uppercase tracking-wider text-danger">{RECALL_VERDICT[r.verdict] ?? r.verdict}</p>
              <p className="mt-1 font-semibold">{r.title}</p>
              {r.hazard && <p className="mt-1">{r.hazard}</p>}
              {r.remedy && <p className="mt-1 text-muted">What to do: {r.remedy}</p>}
              {r.url && <p className="mt-1 break-all text-xs text-muted">{r.url}</p>}
            </div>
          ))}
        </section>
        {pass.hazard && (
          <section className="mt-8">
            <h2 className="font-display text-lg font-bold">Hazard assessment · {pass.hazard.label ?? 'not enough evidence'}</h2>
            <p className="text-xs text-muted">Scored by {pass.hazard.model_code}. Higher means more hazardous.</p>
            <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[32rem] text-left text-sm print:min-w-0">
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
            </div>
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
