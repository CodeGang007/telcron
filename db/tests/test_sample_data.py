"""The fictional demo data (db/seeds/dev/sample_data.sql) obeys the product's rules: no hazard score
without a hazard assessment behind it, and every passport is what the application's own passport
rule would issue for the same inputs (DEF-010)."""
import importlib.util
from decimal import Decimal

from conftest import ROOT, one

SAMPLE = ROOT / "db" / "seeds" / "dev" / "sample_data.sql"
DEMO_SLUGS = ("acme-powerblend-1000", "contoso-fastcharge-65w", "northwind-chillmate-31")


def passport_rules():
    """backend/app/domain/passport.py is pure (dataclasses and Decimal), so it loads without the app."""
    spec = importlib.util.spec_from_file_location(
        "telcron_passport_rules", ROOT / "backend" / "app" / "domain" / "passport.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def current_passports(db):
    return db.execute("""
        SELECT pr.public_slug, pp.version, pp.tier, pp.status_badge, pp.trust_score, pp.recall_component,
               pp.certification_component, pp.hazard_component, pp.hazard_assessment_id, pp.formula_version,
               s.verdict,
               (SELECT coalesce(array_agg(c.status::text ORDER BY c.status), '{}')
                  FROM product_certifications pc
                  JOIN LATERAL (SELECT status FROM certification_checks
                                 WHERE product_certification_id = pc.id
                                 ORDER BY checked_at DESC LIMIT 1) c ON true
                 WHERE pc.product_id = pr.id) AS cert_statuses
          FROM products pr
          JOIN passports pp ON pp.id = pr.current_passport_id
          LEFT JOIN screenings s ON s.id = pp.screening_id
         WHERE pr.public_slug = ANY(%s)
         ORDER BY pr.public_slug""", (list(DEMO_SLUGS),)).fetchall()


def test_no_demo_passport_carries_a_hazard_score_without_an_assessment(db):
    db.execute(SAMPLE.read_text())
    assert one(db, """SELECT count(*) FROM passports
                       WHERE hazard_component IS NOT NULL AND hazard_assessment_id IS NULL""") == 0


def test_demo_passports_are_what_the_passport_rule_would_issue(db):
    db.execute(SAMPLE.read_text())
    rules = passport_rules()
    rows = current_passports(db)
    assert [r[0] for r in rows] == sorted(DEMO_SLUGS)
    for slug, _v, tier, badge, trust, recall, cert, hazard, _a, formula, verdict, statuses in rows:
        expected = rules.build(verdict, list(statuses), None)
        assert (tier, badge, trust, recall, cert, hazard) == (
            expected.tier, expected.status_badge, expected.trust_score, expected.recall_component,
            expected.certification_component, expected.hazard_component), slug
        assert formula == rules.FORMULA_VERSION, slug


def test_a_database_with_the_earlier_demo_passports_is_corrected_once(db):
    db.execute(SAMPLE.read_text())
    # The earlier sample data issued these: a hazard component of 100 with no assessment. Recreate that
    # state as a newer version (passports are append-only), then load the file again as a deploy would.
    db.execute("""
        INSERT INTO passports (product_id, version, tier, status_badge, trust_score, recall_component,
                               certification_component, hazard_component, screening_id, formula_version)
        SELECT pp.product_id, pp.version + 1, pp.tier, pp.status_badge, 96, pp.recall_component,
               pp.certification_component, 100, pp.screening_id, 'trust-v1'
          FROM products pr JOIN passports pp ON pp.id = pr.current_passport_id
         WHERE pr.public_slug = 'northwind-chillmate-31'""")
    stale = one(db, """SELECT pp.id FROM products pr JOIN passports pp ON pp.id = pr.current_passport_id
                        WHERE pr.public_slug = 'northwind-chillmate-31'""")
    db.execute("INSERT INTO passport_evidence (passport_id, evidence_id, purpose) "
               "SELECT %s, evidence_id, purpose FROM passport_evidence pe JOIN passports p ON p.id = pe.passport_id "
               "JOIN products pr ON pr.id = p.product_id "
               "WHERE pr.public_slug = 'northwind-chillmate-31' AND p.version = 1", (stale,))

    db.execute(SAMPLE.read_text())
    slug, version, _t, badge, trust, _r, _c, hazard, _a, formula, *_ = next(
        r for r in current_passports(db) if r[0] == "northwind-chillmate-31")
    assert (version, badge, trust, hazard, formula) == (3, "verified", Decimal("95.00"), None, "provisional-0")
    assert one(db, """SELECT count(*) FROM passport_evidence pe JOIN products pr ON pr.current_passport_id = pe.passport_id
                       WHERE pr.public_slug = 'northwind-chillmate-31'""") == 1

    db.execute(SAMPLE.read_text())  # a further load changes nothing
    assert one(db, """SELECT max(pp.version) FROM passports pp JOIN products pr ON pr.id = pp.product_id
                       WHERE pr.public_slug = 'northwind-chillmate-31'""") == 3
