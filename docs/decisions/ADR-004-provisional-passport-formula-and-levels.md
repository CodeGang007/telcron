# ADR-004 — Provisional passport formula and reward levels

Date: 2026-11-15 · Status: accepted (provisional)

The v2 document defines the hazard formula but not how recall, certification and hazard combine into a passport trust score, tier and badge (technical documentation 7.5, open point 2). To have something to run, `backend/app/domain/passport.py` uses a placeholder, stored on every passport as `formula_version = provisional-0`: trust = 0.4 × recall + 0.2 × certification + 0.4 × (100 − hazard); a confirmed recall always reads `recalled`; high hazard reads `blocked`. Likewise the level names between Novice and Master and every level threshold in `seed.py` are invented. **These numbers are placeholders, not a recommendation.** Telcron must agree the real ones; passports issued meanwhile can be re-issued, since passports are derived data.
