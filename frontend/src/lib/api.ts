const ORIGIN = import.meta.env.VITE_API_URL ?? 'http://localhost:4310';
const BASE = ORIGIN + '/api/v1';
/** A path the API returns (such as a product photo) as a full URL. */
export const apiUrl = (path: string) => ORIGIN + path;
const KEY = 'telcron.session';

export type Tokens = { access_token: string; refresh_token: string };
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    /** Seconds from the Retry-After header of a 429, when the server sent one. */
    public retryAfter: number | null = null,
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

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  let res = await raw(path, init, session.get()?.access_token);
  if (res.status === 401 && session.get()) {
    const next = await refresh();
    if (next) res = await raw(path, init, next.access_token);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const wait = Number(res.headers.get('Retry-After'));
    throw new ApiError(res.status, typeof body.detail === 'string' ? body.detail : 'request_failed',
      Number.isFinite(wait) && wait > 0 ? wait : null);
  }
  return res;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await request(path, init);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

/** One page of a list endpoint. The server says whether another page follows. */
export async function apiPage<T>(path: string, offset: number, limit: number): Promise<{ items: T[]; hasMore: boolean }> {
  const sep = path.includes('?') ? '&' : '?';
  const res = await request(`${path}${sep}offset=${offset}&limit=${limit}`);
  return { items: (await res.json()) as T[], hasMore: res.headers.get('X-Has-More') === 'true' };
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });

export const MESSAGES: Record<string, string> = {
  invalid_credentials: 'That email and password do not match.',
  email_not_verified: 'Confirm your email first: enter the code we emailed you.',
  invalid_or_expired_code: 'That code is wrong or has expired.',
  already_reviewed: 'You have already reviewed this product.',
  already_in_wallet: 'This product is already in your wallet.',
  wallet_full: 'Your wallet is full. Remove a product to save another.',
  flag_pending: 'You already have a report on this product waiting for review.',
  report_pending: 'You already have a correction to that field waiting for review.',
  own_contribution: 'You cannot decide on your own contribution. Leave it for a colleague.',
  review_task_closed: 'Someone has already decided this one.',
  already_decided: 'This has already been decided.',
  role_not_allowed: 'Your account is not allowed to do this.',
  photo_identification_unavailable: 'Reading photos is not available right now. Type the details instead.',
  photo_unreadable: 'That photo could not be read. Try a JPEG or PNG under 3 MB.',
  unknown_category: 'Choose one of the listed categories.',
  assistant_quota_reached: 'You have asked a lot today. The assistant is available again tomorrow.',
  thread_not_found: 'That conversation is not available.',
  research_not_due: 'This product was searched in the last day. It can be searched again tomorrow.',
  research_daily_limit: 'Telcron has used today\'s web-search allowance. New products are researched automatically as it frees up.',
  research_month_limit: 'Telcron has used this month\'s web-search allowance. Research resumes when it renews.',
  research_disabled: 'Web research is switched off right now.',
  product_not_found: 'We could not find that product.',
  invalid_barcode: 'That is not a valid barcode. Check the digits and try again.',
  product_not_identified: 'We could not find that barcode anywhere yet. Try searching by name.',
  lookup_unavailable: 'The product database is busy right now. Try again in a minute.',
  identify_quota_reached: 'You have reached today\'s scan limit. It resets tomorrow.',
  not_enough_coins: 'You do not have enough confirmed TelCoins for that yet.',
  bad_date_range: 'Choose a start date before the end date, at most a year apart.',
  phone_in_use: 'That phone number is already verified on another account.',
  verification_level_1_required: 'Confirm your email to do this: enter the code we emailed you.',
  rate_limited: 'Too many tries from here. Wait a few minutes, then try again.',
  item_not_available: 'That reward is not available right now. Your TelCoins were returned; choose another.',
  item_not_found: 'That reward is no longer offered. Reload the page to see what is.',
  product_required: 'This reward is for one product. Choose one from your wallet first.',
  research_user_daily_limit: 'You have started today\'s share of web searches. You can ask again tomorrow.',
  listing_not_found: 'That listing has changed since it was shown. Reload the page and try again.',
  not_authenticated: 'Sign in to continue.',
};
/** "in 3 minutes" for a Retry-After in seconds, rounded up; "in a moment" under a minute. */
function inMinutes(seconds: number) {
  const m = Math.ceil(seconds / 60);
  return seconds < 60 ? 'in a moment' : `in ${m} minute${m === 1 ? '' : 's'}`;
}

export const explain = (e: unknown) => {
  if (!(e instanceof ApiError)) return 'Cannot reach Telcron. Check your connection and try again.';
  if (e.code === 'rate_limited' && e.retryAfter) return `Too many tries from here. Try again ${inMinutes(e.retryAfter)}.`;
  return MESSAGES[e.code] ?? 'Something went wrong. Try again.';
};

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
  image_url: string | null;
  demo: boolean;
};
export type Finding = {
  kind: 'recall' | 'safety_warning' | 'complaint' | 'review' | 'certification' | 'no_issue_found' | 'general';
  title: string; source: string; about_this_product: boolean; url: string; finding: string; found_at: string;
};
export type Research = {
  enabled: boolean; status: string | null; searched_at: string | null; can_request: boolean;
  // Why a search cannot start now (an error code from MESSAGES), or null.
  blocked: string | null;
  // A queued or running search has empty stats: every field may be missing.
  stats: Partial<{ cpsc_notices: number; cpsc_new: number; pages: number; findings: number; errors: string[] }> | null;
  findings: Finding[];
  progress: { stage: string; percent: number } | null;
  unread: number;
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
