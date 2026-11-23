# WO-059: QA verdict (DEF-117, watchlist_3 off sale and refunded; CT-004)

qa-test-engineer · 2026-11-23 · branch `week-02` @ ca8d67c (commits 1486162, 936331f, 4c4dd5e, ca8d67c, a56e10a).
Local only, nothing pushed. The dev stack (`make dev`) stayed stopped. I read the dev DB (localhost:5440) inside
`BEGIN READ ONLY ... ROLLBACK`.

## Verdict: APPROVE WITH NITS
Every schema, ledger and API line of the acceptance list passes, checked against the code, the tests and the dev
database. All four gates passed. I ran them one at a time (DEF-122). Every mutation I made turned the suites red, and
I restored each file. The one browser line (/rewards shows only the report, no console errors) passed a code reading
only. browser-qa-engineer gives the browser verdict on it. There are no blockers.

## Per criterion
| # | Criterion | Result | Evidence |
| --- | --- | --- | --- |
| 1 | New migration sets `watchlist_3.is_active = false`; no applied migration edited | PASS | `db/migrations/20261123130000_watchlist_off_sale_refund.sql` is new. 1486162 touches no other migration. Dev DB: `schema_migrations` has 20261123130000; `watchlist_3 f`, `hazard_report_pdf t`, the other 4 `f`. |
| 2 | Every fulfilled watchlist_3 redemption refunded through a `coin_*` fn; one confirmed refund per redemption; balance +spend; lifetime unchanged; `refunded`; entitlement removed; pay-once; append-only | PASS | Dev DB: 2 redemptions are `refunded` and kept `fulfilled_at`. `fulfilment.refund.revoked_entitlements` snapshots 1 `watchlist_slots × 3` row each. There are 0 entitlements left. Each has one `refund +100 confirmed` with `reverses_entry_id` = the −100 spend and key `refund:<spend>`. Balances are 180/230 and 105/105 (confirmed/lifetime), and confirmed equals the ledger's confirmed sum for both users. 0 mismatched balances DB-wide. Tests: `test_a_second_refund_pays_nothing`, `test_the_refund_entry_is_append_only`. |
| 3 | The refund cannot refund a fulfilled redemption of an item still on sale | PASS | The guard requires `fulfilled`, item `is_active = false` (read FOR SHARE), `fulfilment_type = 'watchlist_slots'`, only `watchlist_slots` entitlements and no watch using them. Tests: `test_a_delivered_hazard_report_is_refused_on_or_off_sale`, `test_a_watchlist_redemption_is_refused_while_the_item_is_on_sale`. Both go red under mutation b1 (below). |
| 4 | `GET /rewards` store = only `hazard_report_pdf` | PASS | `router.py` filters `is_active`. `test_the_store_lists_only_the_printable_report`. |
| 5 | `POST /redemptions watchlist_3` → 409 `item_not_on_sale`, no spend or redemption; unknown → 404 | PASS | `rewards/service.py:124-125, :139`. Tests `test_the_watchlist_item_is_not_on_sale_and_takes_nothing` and `test_an_unknown_item_is_not_found`. |
| 6 | /rewards shows only the report, no console errors | PASS (code), browser pending | `CoinStore.tsx` renders `items` and hard-codes no item. It handles one item (`GRID[1]`) and an empty store. The message is in `api.ts`. The journey redeems the report but does not assert that the watchlist is absent or that the console is clean. |
| 7 | Four gates pass, run one at a time | PASS | See below. |

## Gates (run by me, one at a time)
- `make db-test`: `119 passed in 4.15s`
- `make api-test`: ruff `All checks passed!` · `179 passed, 4 warnings in 32.98s` (existing Starlette HTTP_422 deprecation)
- `npx tsc --noEmit`: exit 0 · `npm run build`: `✓ built in 3.59s`
- `PW_CHANNEL=chromium npm run journey`: `9 passed (54.2s)`, then `removed: ... Redis index 9, database telcron_e2e_1795438465_712823`
- Left behind: 0 `telcron_e2e_*` DBs, Redis db 9 `dbsize` 0, ports 4310/4311/3200/3201 free, no `tc-lane` containers.

## Revert-proof (each restored with `git checkout -- <path>` straight after)
| Mutation | Result |
| --- | --- |
| a1. `service.py` ← `4c4dd5e~1` | `3 failed, 10 passed` (not_on_sale, off_sale, mid-request race) |
| a2. Delete only the `if not item.is_active` pre-check | `13 passed`. See N1. |
| b1. Delete the `IF it.is_active` guard in the migration's function | `2 failed, 117 passed` (hazard report on/off sale, watchlist on sale) |
| b2. Comment out `UPDATE redemption_items SET is_active = false` | `5 failed, 114 passed` |
| b3. Comment out the `coin_balances` restore in the function | `3 failed, 116 passed` |
After the run, `git status --short` shows only `?? docs/database/db_erds.zip`, which was already there before QA. No mutation was committed.

## Nits (not blocking)
- **N1.** The server-side pre-check is not proven on its own. With it removed, coin_redeem's TC011 backstop gives the same 409 and the spend rolls back in the savepoint, so every test still passes. The visible result matches CT-004. The only gap is the precedence of 409 over 422 for an off-sale `pdf_report` item, and no such item exists. A test that asserts `coin_redeem` is never called would close it (community-rewards-engineer).
- **N2.** Lane C (a56e10a) has no report and no gate results in the WO-059 log.
- **N3.** Lane B's own flag: `router.py` resolves `product` first, so an off-sale item sent with an unknown product gets 404 `product_not_found`. Nothing is spent either way.
- **N4.** The AWS dev DB is not migrated yet. The next release refunds whatever `watchlist_3` buyers exist there.
