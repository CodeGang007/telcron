# WO-059: browser verdict (DEF-117, CT-004)

browser-qa-engineer · 2026-11-23 · local stack (`make dev`: API :4310, Worker, web :3200), branch `week-02` @ ada5a46.
Persona: member L1 `qa-browser-1795287170@example.com`, one of the two members whose `watchlist_3` redemption the
migration refunded. Its password is not recorded anywhere, so a session was opened for it locally through the app's
own `identity.service._open_session` and put in `localStorage['telcron.session']` (local DB only; the token file was
deleted afterwards). Stack stopped afterwards; nothing is listening on 4310 or 3200.

## Verdict: PASS

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Store shows only the printable report; watchlist absent; single card lays out at desktop and 390 px | PASS | `GET /rewards` `store` = `[hazard_report_pdf]` only. Page text has no "Watchlist". Desktop 1516 px: one card, 384 px wide, left-aligned under the heading (`GRID[1]`, `sm:max-w-sm`), no empty grid cells. Phone: same-origin 390 px frame (the Chrome window would not resize), card x=16 w=340, `scrollWidth` 372 < viewport 387, no horizontal scroll. |
| 2 | Balance reflects +100 refund; history shows it | PASS | Balance card 180 confirmed / 230 earned in total (QA: 80/230 before the migration). History, top entry: "Refund · 11/23/2026, 6:17:13 PM · Confirmed · +100". The earlier "Spent in the store −100" is still listed. |
| 3 | `POST /redemptions watchlist_3` → 409 `item_not_on_sale`, balance unchanged | PASS | fetch from the page with a new `request_id`: `409 {"detail":"item_not_on_sale"}`. Balance before and after: `{confirmed:180, pending:0, frozen:0, lifetime_earned:230}`. Unknown code `no_such_item`: `404 {"detail":"item_not_found"}`. DB: no new `watchlist_3` redemption. |
| 4 | Forced stale store shows the message and reloads the store | PASS | `window.fetch` was patched to add `watchlist_3` to `GET /rewards`. The card rendered with Redeem enabled. The patch was switched off, then Redeem was clicked. Result: `POST /redemptions` 409, a red toast "That reward is not on sale right now. Reload the page to see what is.", then `GET /rewards` refetched. The watchlist card was gone and only the report card stayed. Balance stayed 180. |
| 5 | No console errors; no failed calls except the expected 409 | PASS | Console: only two logs from a browser extension (`[Redirect Blocker]`), nothing from the app. API log for the session: 409 (fetch probe), 404 (deliberate unknown-code probe), 409 (UI), 201; every other call 2xx. Four 401s came before the session was injected: a stale session left in the browser from an earlier run. They were followed by `/auth/refresh`, with no storm, and are not WO-059's. |
| 6 | Redeeming the hazard report still works | PASS | `/rewards?product=northwind-chillmate-31` pre-selects the product, Redeem → `201`, confetti, toast "Full hazard report (printable) is yours / Your report is ready. [Open]", balance 180 → 130. After reload: 130, history top "Spent in the store −50 Confirmed". DB: new `hazard_report_pdf` redemption `fulfilled`. |

## Notes (not defects)
- `GET /rewards`, `/wallet/items` and `/contributions` are each requested twice per mount. This is React StrictMode
  in the dev build.
- Screenshots: `/tmp/claude-chrome-screenshots-GGaCEv/` (desktop store, forced stale card, toast, 390 px store,
  redeem success).

## Not tested
- The second refunded member (`qa-final-memberd-…`). The refund is the same migration, and QA checked it in the DB.
- A real narrow Chrome window. The 390 px check used a same-origin iframe.
