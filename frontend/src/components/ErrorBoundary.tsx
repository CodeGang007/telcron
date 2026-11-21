import { RefreshCw, TriangleAlert } from 'lucide-react';
import { Component, type ReactNode } from 'react';

/** A crash in one section shows this instead of a blank page. `section` keeps the rest of the page. */
export class ErrorBoundary extends Component<{ children: ReactNode; section?: string }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.error('[telcron] render failed', error);
  }
  render() {
    if (!this.state.failed) return this.props.children;
    if (this.props.section)
      return <p className="rounded-2xl bg-panel px-4 py-3 text-sm text-muted">The {this.props.section} could not be shown. Reload the page to try again.</p>;
    return (
      <div className="container-page grid place-items-center py-24 text-center">
        <span className="grid size-14 place-items-center rounded-2xl bg-warn-tint text-warn"><TriangleAlert className="size-7" /></span>
        <h1 className="mt-5 font-display text-2xl font-bold">Something went wrong on this page</h1>
        <p className="mt-2 max-w-md text-muted">Your data is safe. Reloading usually fixes it; if not, go back to the home page.</p>
        <div className="mt-6 flex gap-3">
          <button className="btn" onClick={() => window.location.reload()}><RefreshCw className="size-4" />Reload</button>
          <a className="btn-ghost" href="/">Home</a>
        </div>
      </div>
    );
  }
}
