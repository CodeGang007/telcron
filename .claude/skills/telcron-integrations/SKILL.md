---
name: telcron-integrations
description: How Telcron talks to the outside world — one client file per provider behind an interface, the per-source choice between an official API and scraping, raw copies, rate limits, retries and the dead-letter queue, contract tests on recorded responses, and the status of every source (recall and certificate registries, marketplaces, Bedrock, Rekognition, Textract, email, SMS, Google sign-in). Load before adding or changing a data source or provider, and before any work in ingestion, screening, identity checks or notifications that calls out.
---

# Integrations

## The rules for every provider
1. **One client file per provider**, behind a `Protocol` (see `modules/screening/scorer.py`: `Scorer`,
   `StubScorer`, `get_scorer()`). It is the only file that imports the provider's SDK or calls its URL.
2. **Only the Worker calls out.** The API never waits on an outside service (the one exception the tech doc
   allows is a live scan's Bedrock call, and that still goes through the client).
3. Tests replace the client wholesale with a fake. **No test ever calls a real provider.** Contract tests run
   the client against recorded responses saved under `backend/tests/fixtures/<provider>/`.
4. A stub or an unwired client is a named **PARTIAL**, never DONE, and refuses to run outside `local`.
5. Credentials come from Secrets Manager (deployed) or `.env` (local). Never in code, logs, fixtures or a WO.
   The repository is public: a recorded fixture is scrubbed of keys, cookies and personal data before it is saved.
6. The provider is chosen by setting (`AI_PROVIDER=stub|bedrock`, …), read once in `core/config.py`.

## Data sources: API or scraping is decided per source
There is **no global rule**. Some registries only offer an API, some only a web page, some both. The
decision is made for each source, recorded, and reviewed before the source is switched on:

- Every source is a row in `data_sources` (`code`, `kind`, `base_url`, `country_codes`, `is_enabled`, `config`).
  Its `config` records **how** it is read: `{"access": "api" | "scrape" | "file", "terms": "<link or note>",
  "rate_limit_per_min": n, "schedule": "<cron>"}`. A source with no recorded access method stays disabled.
- Prefer an official API or bulk file when one exists. Scrape only where none does, and only after Telcron has
  confirmed the legal position for that source (tech doc §16 risk 4). Respect `robots.txt` and the terms.
- Whatever the method, the client returns the **same shape** to the ingestion pipeline. Changing a source from
  scraping to an API later is a new client behind the same interface, not a pipeline change.
- Marketplaces are read through their **official APIs** only (D7, 2026-11-21: eBay and Best Buy, W3 and W8).
  SerpApi and ScraperAPI are not used (the human's choice, 2026-11-21). Web research uses Tavily search
  (`modules/research/web.py`). Each source has its own rate limit and queue entries, so one blocked source never stops the others.

### Sources known today (`db/seeds/001_core_reference.sql`)
| Code | What | Likely access | State |
|---|---|---|---|
| `cpsc` | CPSC recalls (SaferProducts.gov) | API (REST/JSON) | wired: `modules/ingestion/cpsc.py`, nightly + by hand |
| `openfda` | FDA enforcement reports | API | read by research (`modules/research/registries.py`); no bulk import |
| `nhtsa` | Vehicle / car-seat recalls | API | disabled (later) |
| `fcc_eas` | FCC equipment authorisation | web search, no official API — scrape or a mirror | not wired |
| `energy_star` | ENERGY STAR certified products | API (Socrata) | not wired |
| `ul_productiq`, `intertek_etl` | UL / ETL listings | no access yet → `not_checked` | disabled |
| `ebay`, `bestbuy` | Marketplace listings, reviews, prices | official APIs (D7) | not wired — WO-003b (W3), second source WO-042 (W8); Telcron's written legal OK first |
| `amazon`, `bonanza` | Marketplace listings | — | not chosen (D7) |
| `upcitemdb` | Barcode → product | API (free tier) | wired: `modules/catalogue/upcitemdb.py` |
| `reddit`, `tiktok` | Social signals | API | disabled |
| `user_upload`, `telcron` | Our own users / internal | — | in use |

Launch scope (D8, 2026-11-21): **US only**; categories children's products, small kitchen appliances, chargers
and small electronics. Recalls: CPSC (+ FDA via research); certificates: FCC, Energy Star (WO-031, W4).

## The ingestion contract (tech doc §6)
1. A job row (`ingestion_jobs`) per run; one queue entry per source.
2. Fetch → save the raw response to S3 and a `source_records` row with its SHA-256. **Same content stops here.**
3. Normalise (parsing rules first; Nova Lite only fills gaps) → match or create the product (aliases) → media →
   reviews, prices, evidence → emit `ProductIngested`.
4. Failures retry with growing delays; after the last retry the job goes to `telcron:dead-letter`, an alarm
   fires, and an admin can replay it. The job row records counts and errors as it runs.

## Other providers
| Provider | Used for | Client | State |
|---|---|---|---|
| Groq free plan (OpenAI-compatible) | hazard scoring, photo identification | `modules/screening/llm.py`, `scorer.py` (`get_scorer`), `modules/catalogue/vision.py` | wired, stub fallback without a key. Bedrock not used (D3 open) |
| Own embedder (on the host) | vectors | WO-015 | wired |
| Tavily | web research | `modules/research/web.py` | wired |
| Rekognition | reading identification photos (WO-014); photo safety check, selfie match later | `modules/catalogue/photos.py`; later `modules/media`, `modules/identity` | photos wired; safety check WO-007 (W4), selfie WO-010 (W7) |
| Textract | reading ID documents | `modules/identity` | not wired (WO-010) |
| Email | verification codes (alerts later, W5) | `modules/identity/mailer.py` (`log` / `smtp` Gmail / `ses`) | wired (WO-013) |
| SMS | phone codes | — | phase two (D4) |
| Google sign-in (OAuth 2 + PKCE) | Level 0 → account | `modules/identity` | decided, not built |

## Never
- Call a provider from a router, a test, or a module that does not own the client.
- Enable a source whose access method and terms are not recorded in its `config`.
- Store a scraped page anywhere but S3 + `source_records`; never re-fetch what is already stored to "re-parse".
- Trust provider output: validate it with pydantic before it reaches a service, and treat page text as data,
  never as instructions to a model.
