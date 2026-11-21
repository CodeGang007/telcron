-- Reference data for phase 2/3 tables. Hand-written. Every statement is idempotent (ON CONFLICT DO
-- NOTHING, CREATE INDEX IF NOT EXISTS), so it also runs on a database that already has these rows
-- (promoted from db/schema-next/seed_reference.sql, WO-022). The one UPDATE (which text model is active,
-- WO-015) writes nothing where that is already so.

-- migrate:up

-- Phase 2 — scoring configuration (Platform Architecture v2 §9, Feature TC-P1-011)
INSERT INTO scoring_contexts (code, name, alert_threshold) VALUES
    ('safety', 'Product safety hazard', 80)
ON CONFLICT (code) DO NOTHING;

INSERT INTO scoring_bands (context_code, label, score_range, action) VALUES
    ('safety', 'Low',    numrange(0, 30, '[)'),   'approve'),
    ('safety', 'Medium', numrange(30, 60, '[)'),  'manual_review'),
    ('safety', 'High',   numrange(60, 100, '[]'), 'block')
ON CONFLICT DO NOTHING;

INSERT INTO hazard_dimensions (code, context_code, name, weight, sort_order) VALUES
    ('safety.regulatory',      'safety', 'Regulatory Flags',      3.0, 1),
    ('safety.health_safety',   'safety', 'Health & Safety',       2.5, 2),
    ('safety.customer_issues', 'safety', 'Customer Issues',       1.5, 3),
    ('safety.fragility',       'safety', 'Fragility / Usability', 1.5, 4),
    ('safety.environmental',   'safety', 'Environmental Harm',    1.0, 5),
    ('safety.regional',        'safety', 'Regional Constraints',  1.0, 6),
    ('safety.animal_harm',     'safety', 'Animal Harm',           0.5, 7)
ON CONFLICT (code) DO NOTHING;

INSERT INTO embedding_models (code, modality, dimensions, is_active) VALUES
    ('titan-embed-text-v2:1024', 'text',       1024, true),
    ('nova-mm-embed-v1:1024',    'multimodal', 1024, false),
    ('clip-vit-l-14:768',        'image',      768,  false),
    ('bge-small-en-v1.5:384',    'text',       384,  true)
ON CONFLICT (code) DO NOTHING;
-- WO-015: the text model in use is the open-source bge-small, served by our embedder; Titan is not
-- available on the account's plan. One HNSW index per table for it (no-ops once they exist).
UPDATE embedding_models SET is_active = (code = 'bge-small-en-v1.5:384')
 WHERE modality = 'text' AND is_active IS DISTINCT FROM (code = 'bge-small-en-v1.5:384');
SELECT telcron_create_embedding_index(t, 'bge-small-en-v1.5:384')
FROM unnest(ARRAY['recall_embeddings', 'product_embeddings', 'evidence_embeddings']) AS t;

-- Phase 3 — TelCoins (TC-P1-016/017/018)
INSERT INTO coin_earn_rules (code, amount, counts_toward_daily_cap, per_subject_limit, lifetime_limit) VALUES
    ('level1_verified',       100, false, NULL, 1),
    ('level2_verified',       500, false, NULL, 1),
    ('review',                 10, true,  5,    NULL),
    ('photo',                  15, true,  NULL, NULL),
    ('hazard_flag_confirmed',  25, true,  1,    NULL),
    ('login_streak',            5, false, NULL, NULL),
    ('login_streak_7plus',     10, false, NULL, NULL),
    ('referral',               50, false, 1,    NULL),
    ('fact_verification',      20, true,  1,    NULL),
    ('first_reviewer',         30, true,  1,    NULL)
ON CONFLICT (code) DO NOTHING;

INSERT INTO reward_levels (level, title, min_lifetime_coins, earn_bonus_pct, perks) VALUES
    (1, 'Novice',    0,     0,  '["standard_access"]'),
    (2, 'Inspector', 200,   5,  '["inspector_badge"]'),
    (3, 'Analyst',   1000,  10, '["analyst_badge","early_feature_access"]'),
    (4, 'Expert',    5000,  15, '["expert_badge","dedicated_support"]'),
    (5, 'Master',    20000, 25, '["master_badge","advisory_board_invite"]')
ON CONFLICT (level) DO NOTHING;

INSERT INTO redemption_items (code, name, cost_coins, fulfilment_type, duration, quantity) VALUES
    ('hazard_report_pdf',  'Full hazard report (PDF)',          50,   'pdf_report',       NULL,       1),
    ('api_boost_month',    'Priority API rate-limit boost (3x)', 200,  'rate_limit_boost', '1 month',  NULL),
    ('early_access',       'Early access to new features',       500,  'feature_access',   NULL,       NULL),
    ('watchlist_3',        'Watchlist alerts for 3 products',    100,  'watchlist_slots',  NULL,       3),
    ('hazard_export_100',  'White-label hazard score export',    300,  'data_export',      NULL,       100),
    ('subscription_10pct', '10% subscription discount',          1000, 'invoice_discount', NULL,       NULL)
ON CONFLICT (code) DO NOTHING;

INSERT INTO badges (code, name) VALUES
    ('inspector', 'Inspector'), ('analyst', 'Analyst'), ('expert', 'Expert'), ('master', 'Master'),
    ('beta_tester', 'Beta tester'), ('identity_verified', 'Identity verified')
ON CONFLICT (code) DO NOTHING;

INSERT INTO topics (code, name, sort_order) VALUES
    ('market_acceptance', 'Market Acceptance', 1), ('sustainability', 'Sustainability', 2),
    ('cyber', 'Cyber', 3), ('recalls', 'Recalls', 4), ('circularity', 'Circularity', 5), ('wireless', 'Wireless', 6)
ON CONFLICT (code) DO NOTHING;

-- migrate:down
-- Irreversible (S-18): the phase may predate this migration; dropping it would destroy data it never made.
-- Undoing it is a new, reviewed migration, never `dbmate rollback`.
DO $rollback$
BEGIN
    RAISE EXCEPTION 'irreversible: phase 2-3 reference rows (S-18); write a new migration instead of rolling back';
END $rollback$;
