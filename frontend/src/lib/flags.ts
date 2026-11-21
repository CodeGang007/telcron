import { useEffect, useState } from 'react';
import { api } from './api';

type Flags = Readonly<Record<string, true>>;

// One request per page load (CT-001): every hook shares this promise. A failure counts as "no flags
// enabled" for the rest of the load, so an unfinished feature stays hidden rather than half-shown.
let loaded: Flags | null = null;
let pending: Promise<Flags> | null = null;

function parse(body: unknown): Flags {
  const flags = (body as { flags?: unknown } | null)?.flags;
  if (!flags || typeof flags !== 'object') return {};
  const out: Record<string, true> = {};
  for (const [code, on] of Object.entries(flags)) if (on === true) out[code] = true;
  return out;
}

/** Fetch the enabled flags once; later calls get the same answer. */
export function loadFlags(): Promise<Flags> {
  pending ??= api<unknown>('/flags').then(
    (body) => (loaded = parse(body)),
    () => (loaded = {}),
  );
  return pending;
}

/** Whether a feature flag is on. False while loading, on error, and for a flag the server does not list. */
export function useFlag(code: string): boolean {
  const [flags, setFlags] = useState<Flags | null>(loaded);
  useEffect(() => {
    if (flags) return;
    let live = true;
    void loadFlags().then((f) => {
      if (live) setFlags(f);
    });
    return () => {
      live = false;
    };
  }, [flags]);
  return flags?.[code] === true;
}
