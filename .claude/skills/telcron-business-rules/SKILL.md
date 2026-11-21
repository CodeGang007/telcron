---
name: telcron-business-rules
description: The catalogue of Telcron's business rules — verification levels, sessions, TelCoin earning, the ledger and fraud rules, reward levels, redemptions, hazard scoring, recall verdicts, certificate statuses, passports, wallet and alerts — with where each rule is enforced and which source wins when the documents disagree. Load before writing acceptance criteria, before changing any rule-bearing code, and before reviewing a change that touches coins, identity, screening or passports.
---

# Business rules — the acceptance checklist

**Which source wins.** When two sources disagree, the higher one is the rule and the lower one is a
`DEF-###` or an open point, never a quiet choice:

1. The database: `docs/database/schema_spec.py` and `db/**/*_rules.sql` (CHECKs, triggers, `coin_*`).
2. The reference data the database ships: `db/seeds/001_core_reference.sql`, `db/migrations/*_phase2_3_reference.sql`.
3. Decisions: `docs/decisions/ADR-*.md`.
4. Feature List V2 (`../Resources/Telcron_Feature_List_V2.xlsx`, feature ids `TC-P1-###`).
5. The technical documentation (`../Resources/Telcron — Technical Documentation_Updated.pdf`, sections `§n`).
6. Platform Architecture v2 and the Month-1 technical documentation.

Numbers that live in a table (amounts, weights, caps, thresholds) are **rows**, changed without a deploy.
Code reads them; code never hard-codes them.

## §1 Identity (TelcronID) — `TC-P1-001/002`, tech doc §8
| Level | Name | Requires | Unlocks | Coins |
|---|---|---|---|---|
| 0 | Anonymous / pending | nothing | search, scan, read passports | 0 |
| 1 | Basic verified | email code (CHECK `users_chk3`: Level ≥ 1 ⇒ verified email; ADR-006, D4). Phone codes are phase two (`LEVEL1_REQUIRES_PHONE`, off) | reviews, photos, flags, wallet, coins | 100 (`level1_verified`, once) |
| 2 | Fully verified | Level 1 + ID document + selfie match | higher trust score, business API key | 500 (`level2_verified`, once) |
| 3 | Business verified | Level 2 + company documents + domain email | **phase two** | — |

- A verified phone belongs to exactly one account (partial UNIQUE). Signing up with someone else's verified
  number ends in `409 phone_in_use`, never a 500.
- Google sign-in (decided, **not built yet**, W3 WO-025) gives a verified email, which is Level 1 (ADR-006).
- Without phone verification one person can hold several Level 1 accounts; fraud holds and the daily cap
  still apply (ADR-006 risk).
- Link an OAuth identity to an existing account only when the provider says the email is verified.
- Level 2: ID images go to a private S3 prefix, are read (Textract) and matched (Rekognition), then
  **deleted**; only the outcome is kept in `identity_verifications`. No external government database check.
- Trust score 0–100: starts at 10 (Level 1) / 50 (Level 2); every change is a `trust_score_events` row with
  its reason and resulting score.
- Sessions: refresh tokens are stored only as hashes and rotate on every use; a reused token revokes the
  family; a rotated token never outlives its family. Every sign-in, failure and lockout is an `auth_events` row.
- **Open:** session length. `TC-P1-002` asks for 90 minutes absolute / 20 minutes idle; tech doc §8.2 says
  1-hour access tokens and 30-day refresh tokens. The code follows the tech doc today.

## §2 TelCoins — `TC-P1-016/017/018`, tech doc §9
**The ledger is the truth.** Every write goes through `coin_earn`, `coin_confirm_due`, `coin_spend`,
`coin_redeem`, `coin_refund_redemption` (WO-019), `coin_clawback`, `coin_apply_hold`, `coin_resolve_hold` (via `modules/rewards/service.py`).
Never insert or update `coin_ledger_entries` or `coin_balances` directly.

Earn rules (`coin_earn_rules`, reference data):

| Code | Coins | Daily cap? | Limit |
|---|---|---|---|
| `level1_verified` / `level2_verified` | 100 / 500 | no | once |
| `review` | 10 | yes | 5 per product (schema) — see the open point below |
| `photo` | 15 | yes | after the photo passes moderation |
| `hazard_flag_confirmed` | 25 | yes | once per flag, **after** confirmation |
| `fact_verification` | 20 | yes | after a reviewer accepts it |
| `first_reviewer` | 30 | yes | first review of a product platform-wide |
| `login_streak` / `login_streak_7plus` | 5 / 10 | no | per day; doubles after 7 days |
| `referral` | 50 | no | once per referred friend, when the friend reaches Level 1 |

- New coins are `pending`; they confirm after the rule's delay (10 minutes) unless frozen. Only confirmed coins
  can be spent; spending is immediate.
- Daily cap: 500 coins from capped rules (`app_settings rewards.daily_cap`). The last award is trimmed to fit.
- Rapid-fire: 20 earns in 5 minutes (`rewards.rapid_fire_threshold`) opens a `fraud_holds` row and freezes the
  user's pending coins until a person resolves it.
- Every entry has an idempotency key: a retried request never awards twice. A removed review claws its coins
  back; a clawback may take the balance below zero (debt repaid by future earnings). It never happens twice.
- Reward level is derived from **lifetime earned** and never drops when coins are spent: Novice 0, Inspector
  200, Analyst 1 000, Expert 5 000, Master 20 000; earn bonus 0 / 5 / 10 / 15 / 25 %.
- Redemption items exist for six things (reference data); **phase one** offers two: the full hazard report
  (a printable page) and extra watches (tech doc §9.4, D13). The other four are inactive; a redemption is
  never left `processing` — one that cannot be fulfilled is refunded through a `coin_*` function (WO-019). TelCoins can never be bought or exchanged for money.
- **Open:** reviews per product. The schema allows several and pays for five; tech doc §9.1 says one per product
  per user (the API currently refuses a second review with `409 already_reviewed`).

## §3 Hazard scoring — `TC-P1-011/012`, tech doc §7
- Seven dimensions (`hazard_dimensions`, codes `safety.*`): regulatory 3.0 · health & safety 2.5 · customer
  issues 1.5 · fragility 1.5 · environmental 1.0 · regional 1.0 · animal harm 0.5.
- Total = Σ(weight × score) ÷ Σ(weight of the dimensions that were scored). A dimension with no valid citation is
  `insufficient_data` with **no score** — it drops out of both sums. Never score it as zero.
- Bands (`scoring_bands`): 0–29 Low → approve · 30–59 Medium → safety-team queue · 60+ High → block, alert.
  Feature List V2 also names an alert threshold of 80 (`scoring_contexts.alert_threshold`); both are configurable.
- Every citation must point at an `evidence_items` row that was offered to the model. The database refuses a
  scored dimension with no citation (deferred trigger).
- Every model call writes `ai_invocations` (model, prompt version, tokens, cost, latency). `StubScorer` is a
  keyword placeholder: a named PARTIAL, never AI.

## §4 Recalls, certificates, passports — `TC-P1-008/009/010`, Month-1 doc
- Recall verdict: `match` · `near_match` · `no_match_found` · `insufficient_information`. A `match` or
  `near_match` must cite a candidate with that verdict. "No match found" is true **as of** the screening's
  `corpus_synced_at`, never "never recalled".
- Regional recalls reach only users in that country/subdivision; users with no location are alerted.
- Certificate status: `pending` · `valid` · `expired` · `revoked` · `not_found` · `not_checked` · `lookup_failed`.
  An unreachable agency is `lookup_failed`; a scheme without access (UL, ETL today) is `not_checked` —
  neither is ever shown as "not certified".
- Passport: tier 0 unidentified · 1 identified · 2 verified (a completed screening). Badge `verified` ·
  `recalled` · `certification_issue` · `needs_information`. The database enforces: a recall match ⇔ `recalled`;
  tier < 2 ⇒ `needs_information`; tier 2 ⇒ a screening and a trust score; versions go up by one.
- A passport is never edited. A re-screen issues a new version; the product points at the current one.
- **Open:** the trust-score formula (ADR-004, `formula_version provisional-0`). Do not tune it without a decision.

## §5 Wallet, alerts, community — `TC-P1-013/014/021–025/029`
- One active wallet entry per user and product; at most 100 active items (`wallet.max_items`).
- A manual or barcode add needs a matched short video before it can be `active` (database CHECK). Video
  verification and QR labels are **phase two** (tech doc §2.2).
- A risk event is created once per (product, cause); a re-screen never re-alerts. Each affected holder or
  watcher gets one `user_risk_alerts` row; the user confirms or dismisses it.
- Reviews: rating 1–5; one helpful vote per user per review; a contribution is signed with the TelcronID.
  Hazard flags earn coins only after confirmation by a recall match or a moderator.
- Posts, comments, reactions, the commerce feed and price alerts are **phase two**; their tables exist.

## §6 Platform
- A row that belongs to another user is a **404**, never a 403. No account needed to read passports.
- Every significant write is in the append-only `audit_log`.
- Searches are stored only for signed-in users (search history is personal).
- Data collection is decided **per source**: some sources are official APIs, some need scraping. A source is
  enabled only after its access method and terms are recorded (`telcron-integrations`).
