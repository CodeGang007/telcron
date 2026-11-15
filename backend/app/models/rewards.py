"""Rewards (TelCoins) — 12 tables (ERD page 7).

coin_ledger_entries is append-only and is the truth; coin_balances is a stored
total moved in the same transaction as the ledger row.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Integer,
    Interval,
    Numeric,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts, updated


class CoinEarnRule(Base):
    __tablename__ = "coin_earn_rules"
    code = c(Text, primary_key=True)
    amount = c(BigInteger, nullable=False)
    counts_toward_daily_cap = c(Boolean, nullable=False, server_default=text("false"))
    per_subject_limit = c(Integer)
    lifetime_limit = c(Integer)
    confirmation_delay = c(Interval, nullable=False, server_default=text("interval '10 minutes'"))
    is_active = c(Boolean, nullable=False, server_default=text("true"))


class CoinLedgerEntry(Base):
    __tablename__ = "coin_ledger_entries"
    id = pk()
    user_id = fk("users.id")
    entry_type = c(e.ledger_entry_type, nullable=False)
    amount = c(BigInteger, nullable=False)
    status = c(e.ledger_status, nullable=False, index=True)
    rule_code = fk("coin_earn_rules.code", nullable=True, index=False)
    subject_type = c(Text)
    subject_id = c(UUID(as_uuid=True))
    reference_type = c(Text)
    reference_id = c(UUID(as_uuid=True))
    reverses_entry_id = fk("coin_ledger_entries.id", nullable=True, index=False)
    fraud_hold_id = fk("fraud_holds.id", nullable=True, index=False)
    idempotency_key = c(Text, nullable=False, unique=True)
    confirmable_at = ts()
    status_changed_at = ts()
    created_at = created()


class CoinBalance(Base):
    __tablename__ = "coin_balances"
    user_id = fk("users.id", primary_key=True)
    confirmed_balance = c(BigInteger, nullable=False, server_default="0")
    pending_balance = c(BigInteger, nullable=False, server_default="0")
    frozen_balance = c(BigInteger, nullable=False, server_default="0")
    lifetime_earned = c(BigInteger, nullable=False, server_default="0")
    updated_at = updated()


class RewardLevel(Base):
    __tablename__ = "reward_levels"
    level = c(SmallInteger, primary_key=True)
    title = c(Text, nullable=False, unique=True)
    min_lifetime_coins = c(BigInteger, nullable=False, unique=True)
    earn_bonus_pct = c(Numeric(4, 1), nullable=False, server_default="0")
    perks = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class RedemptionItem(Base):
    __tablename__ = "redemption_items"
    code = c(Text, primary_key=True)
    name = c(Text, nullable=False)
    cost_coins = c(BigInteger, nullable=False)
    fulfilment_type = c(e.fulfilment_type, nullable=False)
    duration = c(Interval)
    quantity = c(Integer)
    is_active = c(Boolean, nullable=False, server_default=text("true"))


class Redemption(Base):
    __tablename__ = "redemptions"
    id = pk()
    user_id = fk("users.id")
    item_code = fk("redemption_items.code", index=False)
    ledger_entry_id = fk("coin_ledger_entries.id", index=False, unique=True)
    product_id = fk("products.id", nullable=True, index=False)
    status = c(e.redemption_status, nullable=False, server_default="processing")
    fulfilment = c(JSONB)
    fulfilled_at = ts()
    created_at = created()


class UserEntitlement(Base):
    __tablename__ = "user_entitlements"
    id = pk()
    user_id = fk("users.id")
    source = c(e.entitlement_source, nullable=False)
    redemption_id = fk("redemptions.id", nullable=True, index=False)
    entitlement = c(Text, nullable=False)
    quantity = c(Integer)
    starts_at = ts(nullable=False, now=True)
    ends_at = ts()


class FraudHold(Base):
    __tablename__ = "fraud_holds"
    id = pk()
    user_id = fk("users.id")
    reason = c(Text, nullable=False)
    rule_triggered = c(Text)
    status = c(e.hold_status, nullable=False, server_default="open", index=True)
    resolved_by_user_id = fk("users.id", nullable=True, index=False)
    resolved_at = ts()
    created_at = created()


class Referral(Base):
    """Phase two."""

    __tablename__ = "referrals"
    id = pk()
    referrer_user_id = fk("users.id")
    referred_user_id = fk("users.id", index=False, unique=True)
    status = c(e.referral_status, nullable=False, server_default="pending")
    qualified_at = ts()
    created_at = created()


class UserDailyLogin(Base):
    __tablename__ = "user_daily_logins"
    user_id = fk("users.id", primary_key=True)
    login_date = c(Date, primary_key=True)


class Badge(Base):
    __tablename__ = "badges"
    code = c(Text, primary_key=True)
    name = c(Text, nullable=False)
    description = c(Text)


class UserBadge(Base):
    __tablename__ = "user_badges"
    user_id = fk("users.id", primary_key=True)
    badge_code = fk("badges.code", primary_key=True)
    awarded_at = ts(nullable=False, now=True)
