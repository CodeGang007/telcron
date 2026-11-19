---
name: telcron-performance
description: Telcron's performance and scale bar for every endpoint, query, job and page — the response-time targets, the backend checklist (bounded queries, indexes, no N+1, the passport cache, slow work in the Worker, trigram KNN search), the frontend checklist, the alarms, and how to measure instead of guess. Load before writing or reviewing any query, endpoint, handler or page, and before claiming something is fast enough.
---

# Performance and scale — built in, measured

Targets (tech doc §3.2, §13). A change that misses one is not done:

| What | Target |
|---|---|
| Cached passport read | < 300 ms |
| Live screening | < 3 s text, < 5 s with images (p99) |
| Queue age | no job waits > 10 minutes; any dead-letter entry alarms |
| Cache | passport cache hit ratio ≥ 60 % |
| Database | connections < 80 % of the pool |

## Backend checklist — every endpoint, query and handler
- **Bounded.** Every list has `limit` with a maximum (≤ 50 on public lists) and is ordered by an indexed column.
- **Indexed for its WHERE and ORDER BY.** Look for the index in `docs/database/schema-design.md` §6 or the
  generated SQL; a query that needs a new one is a request to `database-engineer`, not an ad-hoc `CREATE INDEX`.
- **No N+1.** Load what a list shows in one query (joins or `IN (...)`), never a query per row. Count queries in
  the test if a list grows.
- **Select what you show.** Do not load `payload`/`specifications` JSON or embeddings for a summary list.
- **Fuzzy search uses the KNN form** the GiST trigram index serves: `ORDER BY name <-> :q LIMIT n`.
  `similarity(...) > x ORDER BY similarity DESC` falls back to a full scan at volume.
- **Exact identifiers first**: barcode → `product_aliases` (normalised GTIN-14), model → `model_number_normalized`.
- **Cache the passport**, not everything: `telcron:passport:<product_id>`, invalidated when a new version is
  issued. AI results are cached 24 h per product and model version (tech doc §7.3).
- **Slow work goes to the Worker.** Outside calls, image processing, scoring, fan-out and email never run inside
  a request. The API writes the event; the Worker does the work.
- **Fan-out in SQL**, not in a Python loop over users (`telcron_fanout_risk_event`).
- **Append-only growth is bounded**: a nightly re-screen writes a screening only when the verdict or the
  candidate set changed. High-volume logs are partitioned monthly.
- **Cost is performance too**: the small model (Nova Lite) for routine work, the premium model only for scoring;
  every model call logged in `ai_invocations` with tokens and cost; scraping skips unchanged content (SHA-256).

### Known, not yet fixed
- `modules/catalogue/service.py` `search()` ranks with `word_similarity(...) > 0.35` plus `ILIKE '%q%'`, which
  cannot use the GiST index and scans `products` at volume. Move it to the KNN form (owner:
  `catalogue-engineer`) before the catalogue grows past demo size.

## Frontend checklist — every page
- First load of the passport page shows content without waiting on anything but its one API call.
- Lists are paginated or capped; never render hundreds of rows at once.
- Images are the normalised size (≤ 1024 px), lazy-loaded, with width and height set.
- No request waterfalls: fetch what a page needs in parallel; reuse data already loaded.
- One refresh-token call at a time (`src/lib/api.ts`); a retry storm after expiry is a defect.

## Measure, do not guess
```bash
make db-test-perf          # read paths at ~1.3 M rows: index-backed and under budget
docker compose exec db psql -U telcron -d telcron -c "EXPLAIN (ANALYZE, BUFFERS) <query>"
```
- A new read path a member or visitor hits often gets a case in `db/tests/test_performance.py`
  (`database-engineer` owns it): no sequential scan of a large table, under the budget.
- Report numbers with the data volume they were measured at. "Fast on my machine with 4 rows" is not a result.
- The load test (tech doc §14, before go-live) covers passport reads, live screening and a full ingestion run.
