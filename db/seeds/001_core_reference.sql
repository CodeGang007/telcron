-- Core reference data (phase 1). Idempotent: safe to re-run.
-- Values come from Feature List V2, Platform Architecture v2 and the Month-1 technical doc.

INSERT INTO app_settings (key, value, description) VALUES
    ('auth.session_absolute_minutes', '90',  'TC-P1-002: max session validity'),
    ('auth.session_idle_minutes',     '20',  'TC-P1-002: idle timeout'),
    ('auth.max_failed_logins',        '5',   'lockout threshold'),
    ('auth.lockout_minutes',          '15',  'lockout duration'),
    ('auth.otp_ttl_minutes',          '10',  'phone OTP lifetime'),
    ('identify.daily_quota',          '20',  'NFR-02: per-user identifications per day'),
    ('identify.confidence_threshold', '0.75','D-04: below ⇒ escalate / fallback prompt'),
    ('wallet.max_items',              '100', 'FR-12: active wallet items per user'),
    ('rewards.daily_cap',             '500', 'TC-P1-016: max coins earned per day'),
    ('rewards.rapid_fire_threshold',  '20',  'earn events in 5 min that trigger a fraud hold'),
    ('screening.rescreen_hour_utc',   '3',   'nightly re-screen schedule')
ON CONFLICT (key) DO NOTHING;

INSERT INTO data_sources (code, name, kind, base_url, country_codes) VALUES
    ('cpsc',         'CPSC SaferProducts.gov Recalls', 'recall_authority',        'https://www.saferproducts.gov/RestWebServices/Recall', '{US}'),
    ('openfda',      'openFDA Enforcement Reports',    'recall_authority',        'https://api.fda.gov',                                   '{US}'),
    ('nhtsa',        'NHTSA Recalls',                  'recall_authority',        'https://api.nhtsa.gov/recalls',                         '{US}'),
    ('fcc_eas',      'FCC Equipment Authorization',    'certification_authority', 'https://apps.fcc.gov/oetcf/eas',                        '{US}'),
    ('energy_star',  'ENERGY STAR Certified Products', 'certification_authority', 'https://data.energystar.gov',                           '{US}'),
    ('ul_productiq', 'UL Product iQ',                  'certification_authority', 'https://productiq.ulprospector.com',                    '{}'),
    ('intertek_etl', 'Intertek ETL Directory',         'certification_authority', 'https://bpdirectory.intertek.com',                      '{}'),
    ('amazon',       'Amazon Product Advertising API', 'marketplace',             'https://webservices.amazon.com',                        '{US}'),
    ('ebay',         'eBay Browse API',                'marketplace',             'https://api.ebay.com/buy/browse',                       '{US}'),
    ('bestbuy',      'Best Buy Products API',          'marketplace',             'https://api.bestbuy.com',                               '{US}'),
    ('bonanza',      'Bonanza API',                    'marketplace',             'https://api.bonanza.com',                               '{US}'),
    ('upcitemdb',    'UPCitemdb',                      'product_reference',       'https://api.upcitemdb.com',                             '{}'),
    ('reddit',       'Reddit API',                     'social',                  'https://oauth.reddit.com',                              '{}'),
    ('tiktok',       'TikTok API',                     'social',                  'https://open.tiktokapis.com',                           '{}'),
    ('user_upload',  'User uploads',                   'user',                    NULL,                                                    '{}'),
    ('telcron',      'Telcron internal',               'internal',                NULL,                                                    '{}'),
    ('web_search',   'Web search (product research)',  'internal',                NULL,                                                    '{}'),
    ('regulator_web','Web search of safety regulators','recall_authority',        NULL,                                                    '{}'),
    ('community_web','Owner reports: forums, social media, marketplace reviews', 'social', NULL,                                          '{}'),
    ('uk_opss',      'UK Product Safety Alerts and Recalls', 'recall_authority',  'https://www.gov.uk/product-safety-alerts-reports-recalls', '{GB}')
ON CONFLICT (code) DO NOTHING;
UPDATE data_sources SET is_enabled = false WHERE code IN ('reddit', 'tiktok', 'nhtsa', 'ul_productiq', 'intertek_etl');

INSERT INTO certification_schemes (code, name, data_source_code, is_checkable) VALUES
    ('fcc',         'FCC Equipment Authorization', 'fcc_eas',      true),
    ('energy_star', 'ENERGY STAR',                 'energy_star',  true),
    ('ul',          'UL Listed / Recognized',      'ul_productiq', false),
    ('etl',         'Intertek ETL Listed',         'intertek_etl', false)
ON CONFLICT (code) DO NOTHING;

INSERT INTO categories (code, name, config) VALUES
    ('household',        'Household products', '{}'),
    ('food',             'Food items',         '{}'),
    ('electronics',      'Electronics',        '{}'),
    ('appliances',       'Appliances',         '{}')
ON CONFLICT (code) DO NOTHING;
INSERT INTO categories (code, name, parent_id, config)
SELECT v.code, v.name, p.id, v.config::jsonb FROM (VALUES
    ('blenders',          'Blenders',                'appliances', '{"search_query":"blender","max_products":100,"images_per_product":8,"visual_hazard_signals":["exposed_blade","cracked_jar"]}'),
    ('mini_fridges',      'Mini-fridges',            'appliances', '{"search_query":"mini fridge","max_products":100,"images_per_product":8,"visual_hazard_signals":["damaged_cord"]}'),
    ('window_ac',         'Window air conditioners', 'appliances', '{"search_query":"window air conditioner","max_products":100,"images_per_product":8,"visual_hazard_signals":["missing_guard"]}'),
    ('power_adapters',    'Power adapters',          'electronics','{"search_query":"power adapter charger","max_products":100,"images_per_product":8,"visual_hazard_signals":["missing_cert_mark","melted_casing"]}'),
    ('smartphones',       'Smartphones',             'electronics','{"search_query":"smartphone","max_products":100,"images_per_product":8,"visual_hazard_signals":["swollen_battery"]}')
) AS v(code, name, parent, config) JOIN categories p ON p.code = v.parent
ON CONFLICT (code) DO NOTHING;
