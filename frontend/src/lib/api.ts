const BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:4310') + '/api/v1';
const KEY = 'telcron.session';

export type Tokens = { access_token: string; refresh_token: string };
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

export const session = {
  get(): Tokens | null {
    try {
      return JSON.parse(localStorage.getItem(KEY) ?? 'null');
    } catch {
      return null;
    }
  },
  set(tokens: Tokens | null) {
    if (tokens) localStorage.setItem(KEY, JSON.stringify(tokens));
    else localStorage.removeItem(KEY);
    window.dispatchEvent(new Event('telcron:session'));
  },
};

async function raw(path: string, init: RequestInit, token?: string): Promise<Response> {
  return fetch(BASE + path, {
    ...init,
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
}

// One refresh at a time: refresh tokens rotate, so two parallel refreshes would trip the
// reuse detector and sign the user out everywhere.
let refreshing: Promise<Tokens | null> | null = null;
function refresh(): Promise<Tokens | null> {
  refreshing ??= (async () => {
    const current = session.get();
    if (!current) return null;
    const res = await raw('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: current.refresh_token }),
    });
    const next = res.ok ? ((await res.json()) as Tokens) : null;
    session.set(next);
    return next;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res = await raw(path, init, session.get()?.access_token);
  if (res.status === 401 && session.get()) {
    const next = await refresh();
    if (next) res = await raw(path, init, next.access_token);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, typeof body.detail === 'string' ? body.detail : 'request_failed');
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });

const MESSAGES: Record<string, string> = {
  invalid_credentials: 'That email and password do not match.',
  account_locked: 'Too many attempts. Try again in 15 minutes.',
  email_taken: 'An account with this email already exists. Sign in instead.',
  invalid_or_expired_code: 'That code is wrong or has expired.',
  already_reviewed: 'You have already reviewed this product.',
  already_in_wallet: 'This product is already in your wallet.',
  verification_level_1_required: 'Confirm your email and phone to do this.',
  not_authenticated: 'Sign in to continue.',
};
export const explain = (e: unknown) =>
  e instanceof ApiError
    ? (MESSAGES[e.code] ?? 'Something went wrong. Try again.')
    : 'Cannot reach Telcron. Check your connection and try again.';

export type ProductSummary = {
  id: string;
  slug: string;
  name: string;
  model_number: string | null;
  brand: string | null;
  category: string;
  status_badge: string | null;
  trust_score: number | null;
  tier: number | null;
};
export type Citation = { id: string; kind: string; excerpt: string | null; url: string | null };
export type Dimension = {
  code: string;
  name: string;
  weight: number;
  status: string;
  score: number | null;
  justification: string | null;
  citations: Citation[];
};
export type Passport = {
  version: number;
  tier: number;
  status_badge: string;
  trust_score: number | null;
  recall_component: number | null;
  certification_component: number | null;
  hazard_component: number | null;
  formula_version: string;
  verified_at: string;
  hazard: {
    total_score: number | null;
    label: string | null;
    has_insufficient_data: boolean;
    model_code: string;
    dimensions: Dimension[];
  } | null;
  recall_matches: {
    recall_id: string;
    title: string;
    hazard: string | null;
    remedy: string | null;
    url: string | null;
    verdict: string;
    recall_date: string | null;
  }[];
  history: { version: number; status_badge: string; trust_score: number | null; verified_at: string }[];
};
export type ProductDetail = ProductSummary & {
  description: string | null;
  certifications: { scheme: string; identifier: string; status: string; valid_until: string | null }[];
};
export type Review = {
  id: string;
  rating: number;
  title: string | null;
  body: string;
  author: string | null;
  origin: string;
  helpful_count: number;
  created_at: string;
};
export type Me = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  verification_level: number;
  trust_score: number;
};
