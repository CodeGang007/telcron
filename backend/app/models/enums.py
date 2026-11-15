"""PostgreSQL enum types named by the ERD.

The ERD names each enum type but its preview pages do not list the values. The
values here are inferred from the technical documentation (ADR-003). Adding a
value is an Alembic migration by database-engineer; nothing else may change them.
"""

from sqlalchemy import Enum


def _e(name: str, *values: str) -> Enum:
    return Enum(*values, name=name)


# Identity & Access
auth_provider = _e("auth_provider", "password", "google", "apple")
user_status = _e("user_status", "active", "suspended", "deleted")
user_role = _e("user_role", "user", "safety_reviewer", "admin", "business")
token_purpose = _e("token_purpose", "email_verify", "phone_verify", "password_reset")
auth_event_type = _e(
    "auth_event_type",
    "register", "login_success", "login_failure", "lockout", "logout",
    "token_refresh", "token_reuse", "verify_success", "verify_failure", "password_change",
)  # fmt: skip
identity_check_status = _e(
    "identity_check_status", "pending", "processing", "passed", "failed", "expired"
)

# Catalogue & media
product_status = _e("product_status", "active", "merged", "hidden", "pending_review")
identification_source = _e(
    "identification_source", "barcode", "image", "text", "manual", "ingestion"
)
traceability_status = _e("traceability_status", "unknown", "partial", "verified")
alias_type = _e("alias_type", "gtin", "asin", "sku", "mpn", "url", "title")
media_role = _e("media_role", "primary", "gallery", "label", "packaging")
media_kind = _e("media_kind", "image", "video", "document")
moderation_status = _e("moderation_status", "pending", "approved", "rejected")
visibility = _e("visibility", "public", "private", "unlisted")
capture_input = _e("capture_input", "barcode", "photo", "text")
identification_status = _e(
    "identification_status", "pending", "resolved", "unresolved", "failed"
)
embedding_modality = _e("embedding_modality", "text", "image", "multimodal")

# Sources, recalls, certifications
data_source_kind = _e(
    "data_source_kind", "marketplace", "recall_authority", "certification_body", "user", "internal"
)
source_record_type = _e(
    "source_record_type", "product", "review", "price", "recall", "certificate", "search_result"
)
job_trigger = _e("job_trigger", "manual", "schedule", "api")
job_status = _e(
    "job_status", "queued", "running", "succeeded", "failed", "partial", "dead_letter"
)
evidence_kind = _e(
    "evidence_kind", "recall", "certification", "source_record", "media", "review", "hazard_flag"
)
recall_status = _e("recall_status", "active", "closed", "superseded")
recall_identifier_type = _e(
    "recall_identifier_type", "gtin", "model", "serial_range", "batch", "sku"
)
cert_status = _e("cert_status", "valid", "expired", "revoked", "suspended", "unknown")
check_method = _e("check_method", "api", "scrape", "manual")

# Screening, hazard & passport
screening_run_type = _e("screening_run_type", "ingest", "live", "rescreen", "manual")
run_status = _e("run_status", "queued", "running", "succeeded", "failed")
recall_verdict = _e("recall_verdict", "no_match", "possible_match", "confirmed_match")
candidate_verdict = _e("candidate_verdict", "match", "possible", "no_match")
passport_badge = _e(
    "passport_badge", "verified", "caution", "recalled", "blocked", "unverified"
)
dimension_score_status = _e(
    "dimension_score_status", "scored", "insufficient", "not_applicable"
)
evidence_purpose = _e("evidence_purpose", "recall", "certification", "hazard")

# Wallet, pricing, risk
wallet_add_method = _e("wallet_add_method", "scan", "search", "manual")
wallet_item_status = _e("wallet_item_status", "active", "archived")
video_check_result = _e("video_check_result", "match", "mismatch", "inconclusive")
qr_label_status = _e("qr_label_status", "pending", "generated", "failed")
price_alert_status = _e("price_alert_status", "active", "triggered", "paused")
risk_event_type = _e(
    "risk_event_type", "recall", "certification_change", "hazard_change", "price_drop", "hazard_flag"
)
severity = _e("severity", "low", "medium", "high", "critical")
risk_alert_status = _e("risk_alert_status", "new", "seen", "resolved", "dismissed")
notification_channel = _e("notification_channel", "email", "in_app", "push", "sms")
notification_status = _e("notification_status", "queued", "sent", "failed", "read")

# Community
content_origin = _e("content_origin", "user", "scraped")
content_status = _e("content_status", "published", "pending", "hidden", "removed")
reaction_type = _e("reaction_type", "like", "helpful", "warning")
flag_status = _e("flag_status", "open", "confirmed", "rejected")
fact_report_status = _e("fact_report_status", "open", "confirmed", "rejected")

# Rewards
ledger_entry_type = _e("ledger_entry_type", "earn", "spend", "reversal", "adjustment")
ledger_status = _e("ledger_status", "pending", "confirmed", "frozen", "reversed")
fulfilment_type = _e("fulfilment_type", "hazard_report_pdf", "extra_watches", "other")
redemption_status = _e("redemption_status", "pending", "fulfilled", "failed", "refunded")
entitlement_source = _e("entitlement_source", "redemption", "level", "grant")
hold_status = _e("hold_status", "open", "released", "confirmed_fraud")
referral_status = _e("referral_status", "pending", "qualified", "rejected")

# Feed & platform
feed_item_type = _e("feed_item_type", "recall", "product", "post", "review", "article")
feed_action = _e("feed_action", "view", "click", "save", "hide", "share")
actor_type = _e("actor_type", "user", "system", "admin", "api_key")
review_task_type = _e(
    "review_task_type", "screening", "hazard_flag", "fact_report", "fraud_hold", "content"
)
review_task_status = _e("review_task_status", "open", "in_progress", "resolved", "dismissed")
ai_purpose = _e(
    "ai_purpose", "normalise", "spam_check", "recall_prefilter", "hazard_score", "embedding", "identify"
)
