"""Risk Events & Notifications (6) and Pricing (2) — ERD page 6."""

from sqlalchemy import CHAR, Boolean, Numeric, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts, updated


class RiskEvent(Base):
    """Append-only. Derived: always rebuildable from reference and user data."""

    __tablename__ = "risk_events"
    id = pk()
    product_id = fk("products.id")
    event_type = c(e.risk_event_type, nullable=False)
    severity = c(e.severity, nullable=False)
    screening_id = fk("screenings.id", nullable=True, index=False)
    recall_id = fk("recalls.id", nullable=True, index=False)
    certification_check_id = fk("certification_checks.id", nullable=True, index=False)
    hazard_assessment_id = fk("hazard_assessments.id", nullable=True, index=False)
    price_snapshot_id = fk("price_snapshots.id", nullable=True, index=False)
    hazard_flag_id = fk("hazard_flags.id", nullable=True, index=False)
    title = c(Text, nullable=False)
    summary = c(Text)
    detected_at = ts(nullable=False, now=True)


class RiskEventMedia(Base):
    __tablename__ = "risk_event_media"
    risk_event_id = fk("risk_events.id", primary_key=True)
    media_asset_id = fk("media_assets.id", primary_key=True)
    sort_order = c(SmallInteger, nullable=False, server_default="0")


class UserRiskAlert(Base):
    __tablename__ = "user_risk_alerts"
    id = pk()
    user_id = fk("users.id")
    risk_event_id = fk("risk_events.id")
    wallet_item_id = fk("wallet_items.id", nullable=True, index=False)
    price_alert_id = fk("price_alerts.id", nullable=True, index=False)
    status = c(e.risk_alert_status, nullable=False, server_default="new")
    action_taken = c(Text)
    seen_at = ts()
    resolved_at = ts()
    created_at = created()


class Notification(Base):
    __tablename__ = "notifications"
    id = pk()
    user_id = fk("users.id")
    channel = c(e.notification_channel, nullable=False)
    template_code = c(Text, nullable=False)
    payload = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    user_risk_alert_id = fk("user_risk_alerts.id", nullable=True, index=False)
    status = c(e.notification_status, nullable=False, server_default="queued")
    error = c(Text)
    sent_at = ts()
    read_at = ts()
    created_at = created()


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    user_id = fk("users.id", primary_key=True)
    channel = c(e.notification_channel, primary_key=True)
    category = c(Text, primary_key=True)
    enabled = c(Boolean, nullable=False, server_default=text("true"))


class UserDevice(Base):
    """Phase two (push)."""

    __tablename__ = "user_devices"
    id = pk()
    user_id = fk("users.id")
    platform = c(Text, nullable=False)
    push_token = c(Text, nullable=False, unique=True)
    last_seen_at = ts()
    created_at = created()


class PriceSnapshot(Base):
    """Append-only. Collected from week 8 so history exists for phase-two alerts."""

    __tablename__ = "price_snapshots"
    id = pk()
    product_id = fk("products.id")
    data_source_code = fk("data_sources.code", index=False)
    seller_name = c(Text)
    listing_url = c(Text)
    country_code = c(CHAR(2), nullable=False)
    currency = c(CHAR(3), nullable=False)
    price = c(Numeric(12, 2), nullable=False)
    in_stock = c(Boolean)
    observed_at = ts(nullable=False, now=True)


class PriceAlert(Base):
    """Phase two."""

    __tablename__ = "price_alerts"
    id = pk()
    wallet_item_id = fk("wallet_items.id")
    target_price = c(Numeric(12, 2), nullable=False)
    currency = c(CHAR(3), nullable=False)
    status = c(e.price_alert_status, nullable=False, server_default="active")
    last_triggered_at = ts()
    created_at = created()
    updated_at = updated()
