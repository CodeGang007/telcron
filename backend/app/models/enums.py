"""PostgreSQL enum types, mirrored from the designed schema.

The source of truth is `docs/database/schema_spec.py`; these values are copied from the generated
`db/migrations/20261114120000_extensions_and_types.sql`. Do not edit them by hand: change the spec,
regenerate (`make db-gen`), then update this file. `tests/test_schema_drift.py` fails when they differ.
"""
from sqlalchemy import Enum


def _e(name: str, *values: str) -> Enum:
    # create_type=False: the types are created by the SQL migrations, never by SQLAlchemy.
    return Enum(*values, name=name, create_type=False)

user_status = _e("user_status", "pending", "active", "suspended", "deleted")
user_role = _e("user_role", "user", "moderator", "admin")
auth_provider = _e("auth_provider", "google", "facebook", "apple")
token_purpose = _e(
    "token_purpose",
    "email_verification", "phone_otp", "password_reset", "email_change",
)
auth_event_type = _e(
    "auth_event_type",
    "login_succeeded", "login_failed", "logout", "session_refreshed", "session_revoked",
    "token_reuse_detected", "password_reset_requested", "password_changed", "oauth_linked",
    "oauth_unlinked", "account_locked", "account_unlocked", "otp_sent", "otp_failed",
    "email_verified", "phone_verified",
)
identity_check_status = _e("identity_check_status", "pending", "passed", "failed")
product_status = _e("product_status", "active", "discontinued", "flagged", "merged")
identification_source = _e(
    "identification_source",
    "ai_image", "ai_video", "barcode", "text", "ingestion", "manual", "admin",
)
traceability_status = _e("traceability_status", "pending", "traced", "untraceable")
alias_type = _e("alias_type", "gtin", "marketplace_item", "retailer_sku", "other")
media_kind = _e("media_kind", "image", "video")
media_role = _e("media_role", "primary", "gallery", "label", "nameplate", "packaging")
moderation_status = _e("moderation_status", "pending", "approved", "rejected")
visibility = _e("visibility", "private", "public")
capture_input = _e("capture_input", "image", "video", "barcode", "text")
identification_status = _e(
    "identification_status",
    "pending", "identified", "needs_input", "failed",
)
data_source_kind = _e(
    "data_source_kind",
    "recall_authority", "certification_authority", "marketplace", "social",
    "product_reference", "user", "internal",
)
job_trigger = _e("job_trigger", "schedule", "admin", "system", "event")
job_status = _e("job_status", "queued", "running", "succeeded", "partial", "failed", "cancelled")
source_record_type = _e(
    "source_record_type",
    "product_listing", "review", "social_post", "recall", "certification", "price", "other",
)
evidence_kind = _e(
    "evidence_kind",
    "recall", "certification_check", "source_record", "media_region", "review", "hazard_flag",
    "web_document",
)
evidence_purpose = _e(
    "evidence_purpose",
    "identity", "recall", "certification", "hazard", "traceability",
)
recall_status = _e("recall_status", "active", "closed")
recall_identifier_type = _e(
    "recall_identifier_type",
    "gtin", "model_number", "serial_range", "lot_code", "sku", "date_code",
)
cert_status = _e(
    "cert_status",
    "pending", "valid", "expired", "revoked", "not_found", "not_checked", "lookup_failed",
)
check_method = _e("check_method", "api", "manual_review")
screening_run_type = _e("screening_run_type", "initial", "rescreen", "manual")
run_status = _e("run_status", "running", "completed", "failed")
recall_verdict = _e(
    "recall_verdict",
    "match", "near_match", "no_match_found", "insufficient_information",
)
candidate_verdict = _e("candidate_verdict", "match", "near_match", "rejected")
dimension_score_status = _e("dimension_score_status", "scored", "insufficient_data")
passport_badge = _e(
    "passport_badge",
    "verified", "recalled", "certification_issue", "needs_information",
)
embedding_modality = _e("embedding_modality", "text", "image", "multimodal")
wallet_add_method = _e(
    "wallet_add_method",
    "media_grid", "manual", "barcode", "search", "extension",
)
wallet_item_status = _e("wallet_item_status", "pending_verification", "active", "rejected")
video_check_result = _e("video_check_result", "pending", "matched", "mismatch", "failed")
qr_label_status = _e("qr_label_status", "pending", "generated", "failed")
ledger_entry_type = _e(
    "ledger_entry_type",
    "earn", "level_bonus", "spend", "clawback", "adjustment", "refund",
)
ledger_status = _e("ledger_status", "pending", "confirmed", "frozen", "reversed")
fulfilment_type = _e(
    "fulfilment_type",
    "pdf_report", "rate_limit_boost", "feature_access", "watchlist_slots", "data_export",
    "invoice_discount",
)
redemption_status = _e("redemption_status", "processing", "fulfilled", "failed", "refunded")
entitlement_source = _e("entitlement_source", "redemption", "level_perk", "admin")
hold_status = _e("hold_status", "open", "released", "confirmed_fraud")
referral_status = _e("referral_status", "pending", "qualified", "rewarded", "void")
content_status = _e("content_status", "published", "hidden", "removed")
content_origin = _e("content_origin", "user", "ingested")
flag_status = _e("flag_status", "pending", "confirmed", "rejected")
fact_report_status = _e("fact_report_status", "pending", "accepted", "rejected")
reaction_type = _e("reaction_type", "like", "helpful", "concerned", "same_issue")
feed_item_type = _e(
    "feed_item_type",
    "user_upload", "listing", "social_post", "recall", "community_post",
)
feed_action = _e("feed_action", "impression", "open", "save", "share", "hide")
price_alert_status = _e("price_alert_status", "active", "triggered", "cancelled")
risk_event_type = _e(
    "risk_event_type",
    "recall_match", "recall_near_match", "hazard_threshold", "certification_change",
    "price_drop", "community_flag_confirmed",
)
severity = _e("severity", "info", "low", "medium", "high", "critical")
risk_alert_status = _e("risk_alert_status", "new", "seen", "confirmed", "dismissed", "resolved")
notification_channel = _e("notification_channel", "in_app", "email", "push", "sms")
notification_status = _e("notification_status", "queued", "sent", "delivered", "failed", "read")
actor_type = _e("actor_type", "user", "admin", "system", "job", "model")
review_task_type = _e(
    "review_task_type",
    "media_moderation", "hazard_insufficient_data", "certification_manual_review",
    "hazard_flag", "fact_report", "fraud_hold", "identity_verification", "content_report",
)
review_task_status = _e("review_task_status", "open", "in_progress", "resolved", "dismissed")
ai_purpose = _e(
    "ai_purpose",
    "identify", "identify_escalation", "adjudicate", "hazard_score", "annotate", "embed",
    "moderate", "video_verify", "ocr",
)
