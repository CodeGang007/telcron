-- Demo data for building pages locally. FICTIONAL brands, products and recalls — not real safety data.
-- Covers every passport state: Verified, Recalled, Certification issue, Needs information.
-- Idempotent: does nothing if the demo user already exists.

DO $$
DECLARE
    v_demo  uuid := '019a8000-0000-7000-8000-000000000001';
    v_admin uuid := '019a8000-0000-7000-8000-000000000002';
    b_acme uuid; b_north uuid; b_contoso uuid;
    p_blender uuid; p_fridge uuid; p_charger uuid; p_unknown uuid;
    r_blender uuid; rp uuid;
    s uuid; pc uuid; chk uuid; ev uuid; pp uuid;
BEGIN
    IF EXISTS (SELECT 1 FROM users WHERE id = v_demo) THEN
        RAISE NOTICE 'demo data already present — skipping';
        RETURN;
    END IF;

    -- users (passwords are set through the app; demo accounts start without one)
    INSERT INTO users (id, email, email_verified_at, phone_e164, phone_verified_at, display_name, country_code,
                       subdivision_code, time_zone, status, verification_level, trust_score, referral_code)
    VALUES (v_demo,  'demo@telcron.local',  now(), '+15550100001', now(), 'Demo User',  'US', 'US-CA',
            'America/Los_Angeles', 'active', 1, 10, 'DEMO0001'),
           (v_admin, 'admin@telcron.local', now(), '+15550100002', now(), 'Demo Admin', 'US', NULL,
            'UTC', 'active', 1, 50, 'ADMIN001');
    UPDATE users SET role = 'admin' WHERE id = v_admin;

    -- brands
    INSERT INTO manufacturers (name, normalized_name, country_code) VALUES ('Acme Appliances Inc.', 'acme appliances inc', 'US');
    INSERT INTO brands (name, normalized_name, manufacturer_id)
    VALUES ('Acme Kitchen', 'acme kitchen', (SELECT id FROM manufacturers WHERE normalized_name = 'acme appliances inc'))
    RETURNING id INTO b_acme;
    INSERT INTO brands (name, normalized_name) VALUES ('Northwind', 'northwind') RETURNING id INTO b_north;
    INSERT INTO brands (name, normalized_name) VALUES ('Contoso Power', 'contoso power') RETURNING id INTO b_contoso;

    -- products
    INSERT INTO products (category_id, brand_id, manufacturer_id, canonical_name, model_number, model_number_normalized,
                          identification_source, identity_confidence, traceability_status, public_slug, description)
    VALUES ((SELECT id FROM categories WHERE code = 'blenders'), b_acme,
            (SELECT id FROM manufacturers WHERE normalized_name = 'acme appliances inc'),
            'Acme Kitchen PowerBlend 1000 Blender', 'PB-1000', 'PB1000', 'ai_image', 0.94, 'traced',
            'acme-powerblend-1000', '1000 W countertop blender with 64 oz jar')
    RETURNING id INTO p_blender;
    INSERT INTO products (category_id, brand_id, canonical_name, model_number, model_number_normalized,
                          identification_source, identity_confidence, public_slug)
    VALUES ((SELECT id FROM categories WHERE code = 'mini_fridges'), b_north, 'Northwind ChillMate Mini Fridge 3.1 cu ft',
            'CM-31', 'CM31', 'barcode', 0.99, 'northwind-chillmate-31')
    RETURNING id INTO p_fridge;
    INSERT INTO products (category_id, brand_id, canonical_name, model_number, model_number_normalized,
                          identification_source, identity_confidence, public_slug)
    VALUES ((SELECT id FROM categories WHERE code = 'power_adapters'), b_contoso, 'Contoso FastCharge 65W USB-C Adapter',
            'FC-65', 'FC65', 'text', 0.88, 'contoso-fastcharge-65w')
    RETURNING id INTO p_charger;
    INSERT INTO products (category_id, canonical_name, identification_source, identity_confidence, public_slug)
    VALUES ((SELECT id FROM categories WHERE code = 'household'), 'Unidentified desk lamp', 'ai_image', 0.41,
            'unidentified-desk-lamp')
    RETURNING id INTO p_unknown;

    INSERT INTO product_aliases (product_id, alias_type, namespace, alias_value, data_source_code) VALUES
        (p_blender, 'gtin', '', '00012345000017', 'upcitemdb'),
        (p_blender, 'marketplace_item', 'amazon.us', 'B0DEMO0001', 'amazon'),
        (p_fridge,  'gtin', '', '00012345000024', 'upcitemdb'),
        (p_charger, 'gtin', '', '00012345000031', 'upcitemdb'),
        (p_charger, 'retailer_sku', 'bestbuy', '6500001', 'bestbuy');

    -- a (fictional) CPSC-style recall for the blender
    INSERT INTO recalls (data_source_code, external_id, recall_number, title, description, hazard, remedy, recall_date, url, synced_at)
    VALUES ('cpsc', 'DEMO-26-001', '26-DEMO', 'Acme Kitchen PowerBlend 1000 Blenders Recalled Due to Laceration Hazard',
            'The blade assembly can detach from the jar base during use.', 'Laceration hazard',
            'Stop using the blender and contact Acme for a free replacement jar base.', current_date - 20,
            'https://www.cpsc.gov/Recalls', now())
    RETURNING id INTO r_blender;
    INSERT INTO recall_regions (recall_id, country_code) VALUES (r_blender, 'US');
    INSERT INTO recall_products (recall_id, product_name, brand_name, manufacturer_name, sold_from, sold_to)
    VALUES (r_blender, 'PowerBlend 1000 Blender', 'Acme Kitchen', 'Acme Appliances Inc.', '2025-01-01', '2026-06-30')
    RETURNING id INTO rp;
    INSERT INTO recall_product_identifiers (recall_product_id, identifier_type, value, value_normalized) VALUES
        (rp, 'model_number', 'PB-1000', 'PB1000'), (rp, 'gtin', '012345000017', '00012345000017');

    -- Blender: screening = match → passport Recalled
    INSERT INTO screenings (product_id, run_type, corpus_synced_at, model_code, prompt_version)
    VALUES (p_blender, 'initial', now(), 'nova-lite', 'adjudicate-v1') RETURNING id INTO s;
    INSERT INTO screening_matches (screening_id, recall_id, rank, retrieval_score, verdict, confidence, rationale)
    VALUES (s, r_blender, 1, 0.97, 'match', 0.96, 'Exact model number PB-1000 and GTIN listed in the recall.');
    UPDATE screenings SET status = 'completed', verdict = 'match', candidates_considered = 3, completed_at = now(),
                          rationale = 'Model number and GTIN match the recall notice.' WHERE id = s;
    INSERT INTO passports (product_id, version, tier, status_badge, trust_score, recall_component, certification_component,
                           hazard_component, screening_id, formula_version)
    VALUES (p_blender, 1, 2, 'recalled', 12, 0, 70, 100, s, 'trust-v1') RETURNING id INTO pp;
    INSERT INTO evidence_items (kind, recall_id, url, excerpt)
    VALUES ('recall', r_blender, 'https://www.cpsc.gov/Recalls', 'The blade assembly can detach from the jar base during use.')
    RETURNING id INTO ev;
    INSERT INTO passport_evidence (passport_id, evidence_id, purpose) VALUES (pp, ev, 'recall');

    -- Fridge: no match, Energy Star valid → Verified
    INSERT INTO product_certifications (product_id, scheme_code, certificate_identifier, holder_name)
    VALUES (p_fridge, 'energy_star', 'ES-DEMO-31', 'Northwind') RETURNING id INTO pc;
    INSERT INTO certification_checks (product_certification_id, status, method) VALUES (pc, 'valid', 'api') RETURNING id INTO chk;
    INSERT INTO product_certifications (product_id, scheme_code) VALUES (p_fridge, 'ul') RETURNING id INTO pc;
    INSERT INTO certification_checks (product_certification_id, status, method) VALUES (pc, 'not_checked', 'api');
    INSERT INTO screenings (product_id, run_type, corpus_synced_at) VALUES (p_fridge, 'initial', now()) RETURNING id INTO s;
    UPDATE screenings SET status = 'completed', verdict = 'no_match_found', candidates_considered = 5, completed_at = now() WHERE id = s;
    INSERT INTO passports (product_id, version, tier, status_badge, trust_score, recall_component, certification_component,
                           hazard_component, screening_id, formula_version)
    VALUES (p_fridge, 1, 2, 'verified', 96, 100, 85, 100, s, 'trust-v1') RETURNING id INTO pp;
    INSERT INTO evidence_items (kind, certification_check_id, url) VALUES ('certification_check', chk, 'https://data.energystar.gov')
    RETURNING id INTO ev;
    INSERT INTO passport_evidence (passport_id, evidence_id, purpose) VALUES (pp, ev, 'certification');

    -- Charger: FCC grant expired → Certification issue
    INSERT INTO product_certifications (product_id, scheme_code, certificate_identifier, holder_name, valid_until)
    VALUES (p_charger, 'fcc', '2ADEMO-FC65', 'Contoso Power Ltd', current_date - 90) RETURNING id INTO pc;
    INSERT INTO certification_checks (product_certification_id, status, method) VALUES (pc, 'expired', 'api') RETURNING id INTO chk;
    INSERT INTO screenings (product_id, run_type, corpus_synced_at) VALUES (p_charger, 'initial', now()) RETURNING id INTO s;
    UPDATE screenings SET status = 'completed', verdict = 'no_match_found', candidates_considered = 4, completed_at = now() WHERE id = s;
    INSERT INTO passports (product_id, version, tier, status_badge, trust_score, recall_component, certification_component,
                           hazard_component, screening_id, formula_version)
    VALUES (p_charger, 1, 2, 'certification_issue', 60, 100, 0, 100, s, 'trust-v1') RETURNING id INTO pp;
    INSERT INTO evidence_items (kind, certification_check_id, url) VALUES ('certification_check', chk, 'https://apps.fcc.gov/oetcf/eas')
    RETURNING id INTO ev;
    INSERT INTO passport_evidence (passport_id, evidence_id, purpose) VALUES (pp, ev, 'certification');

    -- Unknown lamp: below threshold → Needs information (Tier 0)
    INSERT INTO identification_requests (user_id, input_type, text_query, status, confidence, escalated, resolved_product_id, completed_at)
    VALUES (v_demo, 'text', 'desk lamp', 'needs_input', 0.41, true, NULL, now());
    INSERT INTO passports (product_id, version, tier, status_badge, formula_version)
    VALUES (p_unknown, 1, 0, 'needs_information', 'trust-v1');

    -- demo user's wallet, labels and a review
    INSERT INTO wallet_items (user_id, product_id, add_method, status, nickname)
    VALUES (v_demo, p_blender, 'media_grid', 'active', 'Kitchen blender'),
           (v_demo, p_fridge,  'search',     'active', 'Dorm fridge'),
           (v_demo, p_charger, 'search',     'active', NULL);
    INSERT INTO wallet_labels (user_id, name, color) VALUES (v_demo, 'Kitchen', '#82b366');
    INSERT INTO wallet_item_labels (wallet_item_id, label_id)
    SELECT w.id, l.id FROM wallet_items w, wallet_labels l
     WHERE w.user_id = v_demo AND w.product_id = p_blender AND l.user_id = v_demo AND l.name = 'Kitchen';
    INSERT INTO reviews (product_id, author_user_id, rating, title, body, verified_owner)
    VALUES (p_fridge, v_demo, 4, 'Quiet and compact', 'Keeps drinks cold, a little noisy at night.', true);

    INSERT INTO audit_log (actor_type, action, entity_type, metadata)
    VALUES ('system', 'seed.demo_data', 'database', '{"note": "fictional demo data"}');
END $$;
