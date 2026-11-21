"""
Read-path performance at realistic volume. Loads synthetic data into a separate database, then
checks with EXPLAIN ANALYZE that each main read path (schema-design.md §6) uses an index — no
sequential scan of a large table — and runs well under the latency budget.

Run alone:  pytest db/tests/test_performance.py -s
"""
import json

import psycopg
import pytest

from conftest import ADMIN_DSN, FILES, dsn_for, up_part

PERF_DB = "telcron_perf"
BUDGET_MS = 25.0

LOAD = """
SELECT set_config('telcron.allow_purge', 'on', false);
ALTER TABLE passports DISABLE TRIGGER passports_before_insert;   -- bulk load only; rules are tested elsewhere

INSERT INTO users (email, display_name, referral_code, country_code, status)
SELECT 'u' || g || '@perf.test', 'User ' || g, 'R' || g, (ARRAY['US','GB','CA','DE'])[1 + g % 4], 'active'
  FROM generate_series(1, 50000) g;

INSERT INTO brands (name, normalized_name) SELECT 'Brand ' || g, 'brand ' || g FROM generate_series(1, 2000) g;

INSERT INTO products (category_id, brand_id, canonical_name, model_number, model_number_normalized,
                      identification_source, public_slug)
SELECT (SELECT id FROM categories ORDER BY code OFFSET (g % 5) LIMIT 1),
       (SELECT id FROM brands WHERE normalized_name = 'brand ' || (1 + g % 2000)),
       (ARRAY['Blender','Mini Fridge','Air Conditioner','Charger','Phone'])[1 + g % 5] || ' ' ||
         (ARRAY['Pro','Max','Ultra','Lite','Plus'])[1 + (g / 5) % 5] || ' ' || g,
       'M-' || g, 'M' || g, 'ingestion', 'p-' || lpad(g::text, 8, '0')
  FROM generate_series(1, 100000) g;

INSERT INTO product_aliases (product_id, alias_type, alias_value)
SELECT id, 'gtin', lpad((row_number() OVER ())::text, 14, '0') FROM products;
INSERT INTO product_aliases (product_id, alias_type, namespace, alias_value)
SELECT id, 'marketplace_item', 'amazon.us', 'B' || lpad((row_number() OVER ())::text, 9, '0') FROM products;

INSERT INTO recalls (data_source_code, external_id, title, description, hazard, recall_date, synced_at)
SELECT 'cpsc', 'R' || g,
       (ARRAY['Blender','Space heater','Charger','Crib','Mini fridge'])[1 + g % 5] || ' recalled ' || g,
       'Units sold nationwide ' || g, (ARRAY['fire','laceration','shock','choking','burn'])[1 + g % 5] || ' hazard',
       current_date - (g % 3000), now()
  FROM generate_series(1, 30000) g;
INSERT INTO recall_products (recall_id, product_name, brand_name)
SELECT id, title, 'Brand ' || (1 + (row_number() OVER ()) % 2000) FROM recalls;
INSERT INTO recall_product_identifiers (recall_product_id, identifier_type, value, value_normalized)
SELECT id, 'model_number', 'M-' || (row_number() OVER ()) * 3, 'M' || (row_number() OVER ()) * 3 FROM recall_products;

INSERT INTO screenings (product_id, run_type, status, verdict, corpus_synced_at, completed_at)
SELECT id, 'initial', 'completed', 'no_match_found', now(), now() FROM products;
INSERT INTO screening_matches (screening_id, recall_id, rank, verdict)
SELECT s.id, r.id, 1, 'rejected'
  FROM (SELECT id, row_number() OVER () rn FROM screenings) s
  JOIN (SELECT id, row_number() OVER () rn FROM recalls) r ON r.rn = 1 + s.rn % 30000;
INSERT INTO passports (product_id, version, tier, status_badge, trust_score, screening_id, formula_version)
SELECT product_id, 1, 2, 'verified', 90, id, 'v1' FROM screenings;
UPDATE products p SET current_passport_id = x.id FROM passports x WHERE x.product_id = p.id;

INSERT INTO wallet_items (user_id, product_id, add_method, status)
SELECT u.id, p.id, 'search', 'active'
  FROM (SELECT id, row_number() OVER () rn FROM users) u
  JOIN (SELECT id, row_number() OVER () rn FROM products) p ON p.rn % 50000 = u.rn % 50000;
INSERT INTO wallet_items (user_id, product_id, add_method, status)
SELECT u.id, p.id, 'search', 'active'
  FROM (SELECT id, row_number() OVER () rn FROM users) u
  JOIN (SELECT id, row_number() OVER () rn FROM products) p ON p.rn = 1 + (u.rn * 7) % 100000
ON CONFLICT DO NOTHING;

INSERT INTO coin_ledger_entries (user_id, entry_type, amount, status, rule_code, idempotency_key, created_at)
SELECT u.id, 'earn', 15, 'confirmed', 'photo', 'perf:' || u.id || ':' || g, now() - (g || ' hours')::interval
  FROM users u, generate_series(1, 6) g;

INSERT INTO risk_events (product_id, event_type, severity, screening_id, recall_id, title, detected_at)
SELECT s.product_id, 'recall_near_match', 'medium', s.id, m.recall_id, 'Possible recall', now() - (random() * interval '60 days')
  FROM screenings s JOIN screening_matches m ON m.screening_id = s.id
 WHERE s.product_id IN (SELECT product_id FROM products ORDER BY id LIMIT 40000);
INSERT INTO user_risk_alerts (user_id, risk_event_id, wallet_item_id, created_at)
SELECT w.user_id, e.id, w.id, e.detected_at FROM risk_events e JOIN wallet_items w ON w.product_id = e.product_id;

INSERT INTO feed_items (item_type, data_source_code, recall_id, category_id, country_code, title, published_at)
SELECT 'recall', 'cpsc', r.id, c.id, (ARRAY['US','GB','CA','DE'])[1 + r.rn % 4], r.title,
       r.created_at - (r.rn || ' minutes')::interval
  FROM (SELECT *, row_number() OVER () rn FROM recalls) r
  JOIN (SELECT id, row_number() OVER (ORDER BY code) - 1 AS k FROM categories) c ON c.k = r.rn % 9;

ALTER TABLE passports ENABLE TRIGGER passports_before_insert;
SELECT set_config('telcron.allow_purge', 'off', false);
ANALYZE;
"""

# name, SQL (uses one sample parameter row), large tables that must not be seq-scanned
READ_PATHS = [
    ("Barcode → product (alias lookup)",
     "SELECT p.* FROM product_aliases a JOIN products p ON p.id = a.product_id WHERE a.alias_type = 'gtin' AND a.namespace = '' AND a.alias_value = '00000000054321'",
     ["product_aliases", "products"]),
    ("Public passport page (slug → current passport)",
     "SELECT p.canonical_name, x.* FROM products p JOIN passports x ON x.id = p.current_passport_id WHERE p.public_slug = 'p-00054321'",
     ["products", "passports"]),
    ("Fuzzy product search (trigram)",
     "SELECT id, canonical_name, canonical_name <-> 'Blender Pro 5432' AS distance FROM products ORDER BY canonical_name <-> 'Blender Pro 5432' LIMIT 10",
     ["products"]),
    ("Recall full-text search",
     "SELECT id, title FROM recalls WHERE search_tsv @@ plainto_tsquery('english', 'charger shock') ORDER BY recall_date DESC LIMIT 20",
     ["recalls"]),
    ("Recall by exact model identifier",
     "SELECT rp.recall_id FROM recall_product_identifiers i JOIN recall_products rp ON rp.id = i.recall_product_id WHERE i.identifier_type = 'model_number' AND i.value_normalized = 'M999'",
     ["recall_product_identifiers", "recall_products"]),
    ("Fuzzy recall-product candidates (trigram KNN)",
     "SELECT recall_id FROM recall_products ORDER BY product_name <-> 'Charger recalled 4242' LIMIT 20",
     ["recall_products"]),
    ("A brand's products in name order (search by brand, DEF-080)",
     "SELECT id FROM products WHERE brand_id = (SELECT id FROM brands WHERE normalized_name = 'brand 77') AND status = 'active' ORDER BY canonical_name, id LIMIT 20",
     ["products"]),
    ("Product by model number (new-recall reverse match)",
     "SELECT id FROM products WHERE model_number_normalized = 'M999'",
     ["products"]),
    ("New recall → previously screened products",
     "SELECT s.product_id FROM screening_matches m JOIN screenings s ON s.id = m.screening_id WHERE m.recall_id = (SELECT id FROM recalls WHERE external_id = 'R123')",
     ["screening_matches", "screenings"]),
    ("My wallet (newest first)",
     "SELECT w.*, p.canonical_name FROM wallet_items w JOIN products p ON p.id = w.product_id WHERE w.user_id = (SELECT id FROM users WHERE email = 'u777@perf.test') AND w.deleted_at IS NULL ORDER BY w.created_at DESC LIMIT 50",
     ["wallet_items", "products"]),
    ("Wallet holders of a product (alert fan-out)",
     "SELECT user_id FROM wallet_items WHERE product_id = (SELECT id FROM products WHERE public_slug = 'p-00000777') AND deleted_at IS NULL AND alerts_enabled",
     ["wallet_items"]),
    ("Risk timeline (grouped by day)",
     "SELECT date_trunc('day', created_at) d, count(*) FROM user_risk_alerts WHERE user_id = (SELECT id FROM users WHERE email = 'u777@perf.test') GROUP BY 1 ORDER BY 1 DESC",
     ["user_risk_alerts"]),
    ("TelCoins: today's earned (daily cap check)",
     "SELECT coalesce(sum(amount), 0) FROM coin_ledger_entries WHERE user_id = (SELECT id FROM users WHERE email = 'u777@perf.test') AND entry_type = 'earn' AND created_at >= date_trunc('day', now())",
     ["coin_ledger_entries"]),
    ("Feed: country × category, newest",
     "SELECT id, title FROM feed_items WHERE country_code = 'US' AND category_id = (SELECT id FROM categories WHERE code = 'blenders') ORDER BY published_at DESC LIMIT 30",
     ["feed_items"]),
]


def plan_nodes(node):
    yield node
    for child in node.get("Plans", []):
        yield from plan_nodes(child)


@pytest.fixture(scope="module")
def perf_db():
    with psycopg.connect(ADMIN_DSN, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {PERF_DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {PERF_DB}")
    with psycopg.connect(dsn_for(PERF_DB), autocommit=True) as conn:
        for f in FILES:
            conn.execute(up_part(f.read_text()))
        conn.execute(LOAD)
        counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in
                  ("users", "products", "product_aliases", "recalls", "screenings", "passports", "wallet_items",
                   "coin_ledger_entries", "risk_events", "user_risk_alerts", "feed_items")}
        print("\nPerf dataset:", json.dumps(counts))
    yield dsn_for(PERF_DB)


@pytest.mark.parametrize("name,sql,big_tables", READ_PATHS, ids=[r[0] for r in READ_PATHS])
def test_read_path_uses_indexes(perf_db, name, sql, big_tables):
    with psycopg.connect(perf_db) as conn:
        conn.execute(sql)                                   # warm cache
        plan = conn.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}").fetchone()[0][0]
    nodes = list(plan_nodes(plan["Plan"]))
    seq = [n.get("Relation Name") for n in nodes if n["Node Type"] == "Seq Scan" and n.get("Relation Name") in big_tables]
    ms = plan["Execution Time"]
    used = sorted({n.get("Index Name") for n in nodes if n.get("Index Name")})
    print(f"\n  {name:55s} {ms:7.2f} ms  indexes: {', '.join(used)}")
    assert not seq, f"{name}: sequential scan on {seq}"
    assert ms < BUDGET_MS, f"{name}: {ms:.1f} ms exceeds {BUDGET_MS} ms"
