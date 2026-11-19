---
name: telcron-user-flows
description: What Telcron is for, who uses it, and the end-to-end journeys the product exists to serve — scan or search to passport, sign-up to Level 1, wallet and alerts, contributing and being paid in TelCoins, the safety team's queue, Level 2, business lookups — with what is built today, what is partial and what is phase two. Load BEFORE writing acceptance criteria, before designing or reviewing a screen or endpoint, and when deciding whether something "works".
---

# What Telcron is

A product-safety platform: **"ID.me for products"**. A person scans or searches for a product and reads its
**passport** — recall verdict, certificates and seven hazard scores, each with the evidence behind it. Every
product is one permanent record, however many marketplaces list it. People who verify their identity
(TelcronID) add reviews, photos and hazard flags, and earn TelCoins when a contribution proves useful. When a
saved product's passport changes, its owners are told.

Sources: tech doc §1 and §10, Feature List V2, the Month-1 technical documentation. Rules behind every step:
`telcron-business-rules`.

## Who uses it
| Persona | Role / level | What they need |
|---|---|---|
| Visitor | no account | Find a product and trust what the passport says, in seconds |
| Member | `user`, Level 1 | Keep their products, be warned, contribute, see their coins |
| Verified member | Level 2 | Higher trust, business API eligibility |
| Safety team | `moderator` | Work the review queue: Medium/High hazards, uncited scores, flags, fraud holds |
| Admin | `admin` | Ingestion jobs, categories by configuration, everything the safety team does |
| Business | API key | Read passports, screen a product, receive webhooks — **phase one target, not built** |

## The journeys (tech doc §10.2) and their state on `main`
| # | Journey | Built | Partial / missing |
|---|---|---|---|
| 1 | **Visitor finds a product** — search by text or barcode (`GET /products`), open it, read the passport with evidence and history | yes | `POST /identify` is barcode-only; photo identification waits for vectors (WO-004); camera scan screen |
| 2 | **Sign-up to Level 1** — register, email code, phone code, Level 1, 100 coins pending | yes | codes are not sent anywhere yet (WO-005); on the dev site sign-up is closed; Google sign-in not built |
| 3 | **Wallet** — save a product, see its badge and changes, remove it | yes | labels, watches, video verification and QR labels (phase two) |
| 4 | **Contribute** — review (rating, title, body), helpful vote, hazard flag; coins pending → confirmed by the Worker | yes | photos on reviews and flags (WO-007), fact corrections |
| 5 | **Evidence loop** — a review or confirmed flag triggers a re-screen, a new passport version and, if it changed, a risk event and alerts | yes (Worker) | real scoring (only `StubScorer`); email alerts |
| 6 | **Coins** — balance, history, level, leaderboard | yes | redemptions (`POST /redemptions`), daily sign-in streaks |
| 7 | **Safety team** — `GET /review-tasks` | list only | confirming/rejecting flags, resolving tasks and fraud holds (WO-006) |
| 8 | **Level 2** — ID document + selfie | no | WO-010 (needs a legal basis) |
| 9 | **Ingestion** — admin starts a job, follows it; categories by configuration | no | WO-003 (sources and their access method undecided) |
| 10 | **Business API** — keys, rate limits, `POST /screenings`, webhooks | screening endpoint only | keys and webhooks have no tables (DEF-002, WO-008) |

Screens today (`frontend/src/main.tsx`): home, search, product (passport), sign-in, sign-up/verify, wallet,
rewards, leaderboard. The admin console does not exist yet.

## What each journey must get right
1. **Search and passport** need no account and no sign-in prompt. A cached passport is under 300 ms. A
   product with no screening shows that plainly — never a green badge by default.
2. **The passport is honest**: "no recall found" carries the date it is true as of; `not_checked` and
   `lookup_failed` certificates are never shown as "not certified"; an uncited dimension shows as
   insufficient data, never as zero.
3. **Contributions are signed and paid once.** A repeat of the same action never awards twice; coins show as
   pending until the Worker confirms them; a member sees why coins are frozen.
4. **Alerts reach the right people once**: holders and watchers of that product, in the recall's region, one
   alert per event, with the reason and evidence.
5. **Another user's data is a 404**, from the API and from the screen.

## Writing acceptance criteria
- One journey, one role, stated as observable outcomes: what the person sees, what row exists afterwards, what
  event was emitted. "Given / When / Then" from `TC-P1-###` is a good start — cite the feature id.
- Include the failure states: wrong code, expired code, duplicate, no permission, provider down, empty result.
- For anything asynchronous (re-screen, coin confirmation, alerts), say how long it may take and how the
  person learns it happened.
- A criterion that depends on an open point (`telcron-business-rules` "Open") names it and states the
  assumption used.

## Blast radius — rank defects by this
1. A wrong or misleading passport (a recalled product shown as safe, an invented citation).
2. Coins awarded twice, spendable before confirmation, or lost.
3. Another user's data visible; an ID document kept; a secret exposed.
4. Search or passport broken for visitors.
5. Sign-up or sign-in broken.
6. Wallet, alerts, contributions broken.
7. Everything else.
