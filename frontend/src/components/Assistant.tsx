import { ArrowUp, Bot, ExternalLink, Loader2, ShieldCheck, Sparkles, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api, explain, post } from '../lib/api';
import { useAuth } from '../lib/auth';

type Citation = { label: string; evidence_id: string; kind: string; url: string | null; excerpt: string };
type Message = { role: 'user' | 'assistant'; content: string; citations: Citation[] };
type Conversation = { thread_id: string | null; messages: Message[] };

const SUGGESTIONS = [
  'Has it ever been recalled?',
  'What do owners complain about?',
  'Is it safe to use around children?',
  'Is there a safer alternative?',
];

function host(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return 'source'; }
}

/** Ask anything about one product. Answers come only from what Telcron holds about it, each with
    the sources it rests on; the conversation is remembered per member and product. */
export function Assistant({ slug, name }: { slug: string; name: string }) {
  const { me } = useAuth();
  const [open, setOpen] = useState(false);
  const [thread, setThread] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || !me || loaded) return;
    api<Conversation>(`/products/${slug}/assistant`)
      .then((c) => { setThread(c.thread_id); setMessages(c.messages); })
      .catch(() => undefined)
      .finally(() => setLoaded(true));
  }, [open, me, slug, loaded]);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, busy]);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, []);

  const ask = async (text: string, e?: FormEvent) => {
    e?.preventDefault();
    const question = text.trim();
    if (question.length < 2 || busy) return;
    setDraft('');
    setMessages((m) => [...m, { role: 'user', content: question, citations: [] }]);
    setBusy(true);
    try {
      const r = await post<{ thread_id: string; answer: string; citations: Citation[] }>(
        `/products/${slug}/assistant`, { message: question, thread_id: thread });
      setThread(r.thread_id);
      setMessages((m) => [...m, { role: 'assistant', content: r.answer, citations: r.citations }]);
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: explain(err), citations: [] }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <motion.button
        initial={{ opacity: 0, y: 20, scale: 0.9 }} animate={{ opacity: 1, y: 0, scale: 1 }} whileHover={{ y: -2 }} whileTap={{ scale: 0.96 }}
        onClick={() => setOpen(true)}
        className="fixed bottom-24 right-4 z-30 flex items-center gap-2 rounded-full bg-gradient-to-br from-brand-bright to-brand-deep px-5 py-3.5 text-sm font-semibold text-white shadow-brand lg:bottom-8 lg:right-8"
        aria-label={`Ask about ${name}`}
      >
        <Sparkles className="size-4" />Ask about this product
      </motion.button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} className="fixed inset-0 z-40 bg-ink/30 backdrop-blur-sm" />
            <motion.aside
              role="dialog" aria-modal="true" aria-label="Product assistant"
              initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-white shadow-lift"
            >
              <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
                <div className="flex items-start gap-3">
                  <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-bright to-brand-deep text-white"><Bot className="size-5" /></span>
                  <div>
                    <p className="font-display font-bold leading-tight">Product assistant</p>
                    <p className="line-clamp-1 text-xs text-muted">{name}</p>
                  </div>
                </div>
                <button onClick={() => setOpen(false)} className="grid size-9 place-items-center rounded-full text-muted transition hover:bg-panel hover:text-ink" aria-label="Close"><X className="size-5" /></button>
              </header>

              <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
                <p className="flex items-start gap-2 rounded-2xl bg-panel px-4 py-3 text-xs text-muted">
                  <ShieldCheck className="mt-0.5 size-4 shrink-0 text-ok" />
                  Answers come only from this product's passport, recall registries and the sources we found, and link to them. If they don't say, it will tell you so.
                </p>
                {!me ? (
                  <div className="rounded-2xl border border-line p-5 text-center text-sm">
                    <p className="font-semibold">Sign in to ask questions</p>
                    <p className="mt-1 text-muted">Your conversation is kept so you can come back to it.</p>
                    <Link to="/sign-in" className="btn btn-sm mt-4">Sign in</Link>
                  </div>
                ) : (
                  <>
                    {messages.length === 0 && loaded && (
                      <div className="grid gap-2">
                        {SUGGESTIONS.map((s, i) => (
                          <motion.button key={s} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                            onClick={() => void ask(s)} className="rounded-2xl border border-line px-4 py-3 text-left text-sm transition hover:border-action hover:bg-action-tint/40">
                            {s}
                          </motion.button>
                        ))}
                      </div>
                    )}
                    {messages.map((m, i) => (
                      <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={m.role === 'user' ? 'flex justify-end' : ''}>
                        <div className={m.role === 'user' ? 'max-w-[85%] rounded-3xl rounded-br-lg bg-ink px-4 py-2.5 text-sm text-white' : 'max-w-[92%] rounded-3xl rounded-bl-lg bg-panel px-4 py-3 text-sm'}>
                          <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>
                          {m.citations.length > 0 && (
                            <div className="mt-3 flex flex-wrap gap-1.5">
                              {m.citations.map((c) => c.url ? (
                                <a key={c.label} href={c.url} target="_blank" rel="noreferrer noopener" title={c.excerpt}
                                  className="inline-flex items-center gap-1 rounded-full border border-line bg-white px-2.5 py-1 text-[11px] font-semibold text-action transition hover:border-action">
                                  {host(c.url)}<ExternalLink className="size-3" />
                                </a>
                              ) : (
                                <span key={c.label} title={c.excerpt} className="rounded-full border border-line bg-white px-2.5 py-1 text-[11px] font-semibold text-muted">{c.kind.replace('_', ' ')}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </motion.div>
                    ))}
                    {busy && (
                      <div className="flex items-center gap-2 text-xs text-muted"><Loader2 className="size-4 animate-spin" />Reading the evidence…</div>
                    )}
                  </>
                )}
                <div ref={end} />
              </div>

              {me && (
                <form onSubmit={(e) => void ask(draft, e)} className="border-t border-line p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
                  <div className="flex items-end gap-2 rounded-3xl border border-line bg-white p-1.5 pl-4 focus-within:border-action">
                    <textarea
                      value={draft} onChange={(e) => setDraft(e.target.value)} rows={1} maxLength={1000}
                      onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void ask(draft); } }}
                      placeholder="Ask about recalls, hazards, owners' reports…" aria-label="Your question"
                      className="max-h-32 flex-1 resize-none bg-transparent py-2 text-sm outline-none"
                    />
                    <button className="grid size-9 shrink-0 place-items-center rounded-full bg-ink text-white transition disabled:opacity-30" disabled={busy || draft.trim().length < 2} aria-label="Send">
                      <ArrowUp className="size-4" />
                    </button>
                  </div>
                </form>
              )}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
