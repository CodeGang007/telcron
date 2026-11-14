"""Evidence, certifications, screening, passports and hazard scoring (FR-07…11, TC-P1-009/011)."""
from conftest import make_passport, make_product, make_recall, make_screening, make_user, one, savepoint_raises


# ─────────── evidence ───────────
def test_evidence_has_exactly_one_typed_subject(db):
    r = make_recall(db)
    db.execute("INSERT INTO evidence_items (kind, recall_id, url) VALUES ('recall', %s, 'https://cpsc.gov/x')", (r,))
    savepoint_raises(db, "INSERT INTO evidence_items (kind) VALUES ('recall')", match="evidence_items_chk2")
    savepoint_raises(db, "INSERT INTO evidence_items (kind, url) VALUES ('web_document', NULL)", match="evidence_items_chk2")
    savepoint_raises(db, "INSERT INTO evidence_items (kind, recall_id, bbox) VALUES ('recall', %s, '{1,2,3,4}')", (r,),
                     match="evidence_items_chk1")            # bbox only for image regions
    db.execute("INSERT INTO evidence_items (kind, url) VALUES ('web_document', 'https://example.com')")


def test_evidence_is_immutable(db):
    eid = one(db, "INSERT INTO evidence_items (kind, url) VALUES ('web_document', 'https://a') RETURNING id")
    savepoint_raises(db, "UPDATE evidence_items SET excerpt = 'edited' WHERE id = %s", (eid,), match="append-only")


# ─────────── certifications ───────────
def test_certification_check_updates_current_status(db):
    p = make_product(db)
    pc = one(db, "INSERT INTO product_certifications (product_id, scheme_code, certificate_identifier) VALUES (%s, 'fcc', '2ABCD-123') RETURNING id", (p,))
    assert one(db, "SELECT current_status FROM product_certifications WHERE id = %s", (pc,)) == "pending"
    c1 = one(db, "INSERT INTO certification_checks (product_certification_id, status, method) VALUES (%s, 'valid', 'api') RETURNING id", (pc,))
    one(db, "INSERT INTO certification_checks (product_certification_id, status, method) VALUES (%s, 'lookup_failed', 'api') RETURNING id", (pc,))
    assert one(db, "SELECT current_status FROM product_certifications WHERE id = %s", (pc,)) == "lookup_failed"
    assert one(db, "SELECT count(*) FROM certification_checks WHERE product_certification_id = %s", (pc,)) == 2  # history kept
    savepoint_raises(db, "UPDATE certification_checks SET status = 'expired' WHERE id = %s", (c1,), match="append-only")


def test_certificate_cannot_point_at_another_certificates_check(db):
    p = make_product(db)
    a = one(db, "INSERT INTO product_certifications (product_id, scheme_code, certificate_identifier) VALUES (%s, 'fcc', 'A') RETURNING id", (p,))
    b = one(db, "INSERT INTO product_certifications (product_id, scheme_code, certificate_identifier) VALUES (%s, 'fcc', 'B') RETURNING id", (p,))
    cb = one(db, "INSERT INTO certification_checks (product_certification_id, status, method) VALUES (%s, 'valid', 'api') RETURNING id", (b,))
    savepoint_raises(db, "UPDATE product_certifications SET last_check_id = %s WHERE id = %s", (cb, a),
                     match="product_certifications_last_check_id_id_fkey")


def test_manual_review_needs_reviewer(db):
    p = make_product(db)
    pc = one(db, "INSERT INTO product_certifications (product_id, scheme_code) VALUES (%s, 'ul') RETURNING id", (p,))
    savepoint_raises(db, "INSERT INTO certification_checks (product_certification_id, status, method) VALUES (%s, 'valid', 'manual_review')",
                     (pc,), match="certification_checks_chk1")


# ─────────── screening ───────────
def test_match_verdict_must_cite_a_matching_candidate(db):
    p = make_product(db)
    s = one(db, "INSERT INTO screenings (product_id, run_type, corpus_synced_at) VALUES (%s, 'initial', now()) RETURNING id", (p,))
    savepoint_raises(db, "UPDATE screenings SET status='completed', verdict='match', completed_at=now() WHERE id = %s",
                     (s,), match="cites no match candidate")
    r = make_recall(db)
    make_screening(db, p, verdict="match", recall_id=r)       # cited ⇒ fine
    db.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_completed_screening_is_frozen(db):
    p = make_product(db)
    s = make_screening(db, p)
    savepoint_raises(db, "UPDATE screenings SET verdict = 'match' WHERE id = %s", (s,), match="can no longer change")
    savepoint_raises(db, "UPDATE screenings SET run_type = 'manual' WHERE id = %s", (s,))
    savepoint_raises(db, "UPDATE screenings SET status = 'completed' WHERE id = %s", (s,))


# ─────────── passports ───────────
def test_recall_match_forces_recalled_badge(db):
    p, r = make_product(db), make_recall(db)
    s = make_screening(db, p, verdict="match", recall_id=r)
    savepoint_raises(db, """INSERT INTO passports (product_id, version, tier, status_badge, trust_score, screening_id, formula_version)
                            VALUES (%s, 1, 2, 'verified', 95, %s, 'v1')""", (p, s), match='requires badge "recalled"')
    pid = make_passport(db, p, s, badge="recalled")
    assert one(db, "SELECT current_passport_id FROM products WHERE id = %s", (p,)) == pid   # pointer maintained


def test_recalled_badge_requires_a_match(db):
    p = make_product(db)
    s = make_screening(db, p, verdict="no_match_found")
    savepoint_raises(db, """INSERT INTO passports (product_id, version, tier, status_badge, trust_score, screening_id, formula_version)
                            VALUES (%s, 1, 2, 'recalled', 10, %s, 'v1')""", (p, s), match="requires a match")


def test_tiers_and_versions(db):
    p = make_product(db)
    savepoint_raises(db, """INSERT INTO passports (product_id, version, tier, status_badge, formula_version)
                            VALUES (%s, 1, 1, 'verified', 'v1')""", (p,), match="passports_chk4")    # tier<2 ⇒ needs_information
    savepoint_raises(db, """INSERT INTO passports (product_id, version, tier, status_badge, formula_version)
                            VALUES (%s, 1, 2, 'verified', 'v1')""", (p,), match="passports_chk5")    # tier 2 needs screening+score
    make_passport(db, p, None, badge="needs_information", tier=1)
    savepoint_raises(db, """INSERT INTO passports (product_id, version, tier, status_badge, formula_version)
                            VALUES (%s, 5, 1, 'needs_information', 'v1')""", (p,), match="version must be 2")
    s = make_screening(db, p)
    make_passport(db, p, s)
    assert one(db, "SELECT max(version) FROM passports WHERE product_id = %s", (p,)) == 2


def test_passport_cannot_cite_another_products_screening(db):
    a, b = make_product(db), make_product(db)
    sb = make_screening(db, b)
    savepoint_raises(db, """INSERT INTO passports (product_id, version, tier, status_badge, trust_score, screening_id, formula_version)
                            VALUES (%s, 1, 2, 'verified', 90, %s, 'v1')""", (a, sb), match="passports_screening_id_product_id_fkey")


def test_product_cannot_point_at_another_products_passport(db):
    a, b = make_product(db), make_product(db)
    pb = make_passport(db, b, make_screening(db, b))
    savepoint_raises(db, "UPDATE products SET current_passport_id = %s WHERE id = %s", (pb, a),
                     match="products_current_passport_id_id_fkey")


def test_passports_are_immutable(db):
    p = make_product(db)
    pid = make_passport(db, p, make_screening(db, p))
    savepoint_raises(db, "UPDATE passports SET trust_score = 100 WHERE id = %s", (pid,), match="append-only")


# ─────────── hazard scoring (phase 2) ───────────
def _assessment(db, p):
    return one(db, """INSERT INTO hazard_assessments (product_id, context_code, total_score, label, input_modalities, model_code)
                      VALUES (%s, 'safety', 16.4, 'Low', '{text,image}', 'nova-premier') RETURNING id""", (p,))


def test_scored_dimension_needs_a_citation(db):
    p = make_product(db)
    a = _assessment(db, p)
    savepoint_raises(db, """INSERT INTO hazard_dimension_scores (assessment_id, context_code, dimension_code, status, score, weight_applied)
                            VALUES (%s, 'safety', 'safety.regulatory', 'scored', 60, 3.0)""", (a,), match="without a citation")
    ev = one(db, "INSERT INTO evidence_items (kind, url, excerpt) VALUES ('web_document', 'https://cpsc.gov', 'recalled') RETURNING id")
    db.execute("""INSERT INTO hazard_dimension_scores (assessment_id, context_code, dimension_code, status, score, weight_applied)
                  VALUES (%s, 'safety', 'safety.regulatory', 'scored', 60, 3.0)""", (a,))
    db.execute("INSERT INTO hazard_score_citations (assessment_id, dimension_code, evidence_id) VALUES (%s, 'safety.regulatory', %s)", (a, ev))
    db.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_insufficient_data_has_no_score(db):
    a = _assessment(db, make_product(db))
    savepoint_raises(db, """INSERT INTO hazard_dimension_scores (assessment_id, context_code, dimension_code, status, score, weight_applied)
                            VALUES (%s, 'safety', 'safety.animal_harm', 'insufficient_data', 10, 0.5)""", (a,),
                     match="hazard_dimension_scores_chk1")
    db.execute("""INSERT INTO hazard_dimension_scores (assessment_id, context_code, dimension_code, status, weight_applied)
                  VALUES (%s, 'safety', 'safety.animal_harm', 'insufficient_data', 0.5)""", (a,))
    db.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_dimension_must_belong_to_assessment_context(db):
    db.execute("INSERT INTO scoring_contexts (code, name, alert_threshold) VALUES ('sustainability', 'S', 70)")
    db.execute("INSERT INTO hazard_dimensions (code, context_code, name, weight) VALUES ('sustainability.recyclable', 'sustainability', 'R', 1)")
    a = _assessment(db, make_product(db))
    savepoint_raises(db, """INSERT INTO hazard_dimension_scores (assessment_id, context_code, dimension_code, status, weight_applied)
                            VALUES (%s, 'safety', 'sustainability.recyclable', 'insufficient_data', 1)""", (a,),
                     match="hazard_dimension_scores_dimension_code_context_code_fkey")
    savepoint_raises(db, "INSERT INTO hazard_dimensions (code, context_code, name, weight) VALUES ('bad', 'safety', 'B', 1)",
                     match="hazard_dimensions_chk2")


def test_score_bands_cannot_overlap(db):
    savepoint_raises(db, "INSERT INTO scoring_bands (context_code, label, score_range, action) VALUES ('safety', 'Overlap', numrange(50, 70), 'x')",
                     match="scoring_bands_no_overlap")


def test_embedding_dimensions_must_match_model(db):
    r = make_recall(db)
    savepoint_raises(db, "INSERT INTO recall_embeddings (recall_id, model_code, content_sha256, embedding) VALUES (%s, 'bge-small-en-v1.5:384', 'x', %s::vector)",
                     (r, "[" + ",".join(["0.1"] * 10) + "]"), match="expects 384")
    db.execute("INSERT INTO recall_embeddings (recall_id, model_code, content_sha256, embedding) VALUES (%s, 'bge-small-en-v1.5:384', 'x', %s::vector)",
               (r, "[" + ",".join(["0.1"] * 384) + "]"))
    db.execute("SELECT telcron_create_embedding_index('recall_embeddings', 'bge-small-en-v1.5:384')")
    assert one(db, "SELECT count(*) FROM pg_indexes WHERE tablename = 'recall_embeddings' AND indexdef ILIKE '%%hnsw%%'") == 1
