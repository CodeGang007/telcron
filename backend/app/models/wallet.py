"""Digital Wallet — 6 tables (ERD page 6)."""

from sqlalchemy import Boolean, Numeric, Text, UniqueConstraint, text
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts, updated


class WalletItem(Base):
    __tablename__ = "wallet_items"
    id = pk()
    user_id = fk("users.id")
    product_id = fk("products.id")
    add_method = c(e.wallet_add_method, nullable=False)
    identification_request_id = fk("identification_requests.id", nullable=True, index=False)
    status = c(e.wallet_item_status, nullable=False)
    verified_by_verification_id = fk(
        "wallet_item_verifications.id", nullable=True, index=False, use_alter=True
    )
    nickname = c(Text)
    notes = c(Text)
    alerts_enabled = c(Boolean, nullable=False, server_default=text("true"))
    last_seen_passport_id = fk("passports.id", nullable=True, index=False)
    created_at = created()
    updated_at = updated()
    deleted_at = ts()


class WalletItemVerification(Base):
    __tablename__ = "wallet_item_verifications"
    id = pk()
    wallet_item_id = fk("wallet_items.id")
    media_asset_id = fk("media_assets.id", index=False)
    result = c(e.video_check_result, nullable=False, server_default="pending")
    confidence = c(Numeric(4, 3))
    mismatch_reason = c(Text)
    model_code = c(Text)
    created_at = created()


class WalletLabel(Base):
    __tablename__ = "wallet_labels"
    __table_args__ = (UniqueConstraint("user_id", "name"),)
    id = pk()
    user_id = fk("users.id")
    name = c(Text, nullable=False)
    color = c(Text)
    created_at = created()


class WalletItemLabel(Base):
    __tablename__ = "wallet_item_labels"
    wallet_item_id = fk("wallet_items.id", primary_key=True)
    label_id = fk("wallet_labels.id", primary_key=True)
    created_at = created()


class QrLabel(Base):
    """Phase two."""

    __tablename__ = "qr_labels"
    id = pk()
    wallet_item_id = fk("wallet_items.id")
    provider = c(Text, nullable=False, server_default="")
    template_code = c(Text, nullable=False)
    status = c(e.qr_label_status, nullable=False, server_default="pending")
    external_label_id = c(Text)
    payload_url = c(Text)
    image_media_id = fk("media_assets.id", nullable=True, index=False)
    error = c(Text)
    created_at = created()


class ProductWatch(Base):
    __tablename__ = "product_watches"
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)
    id = pk()
    user_id = fk("users.id")
    product_id = fk("products.id")
    entitlement_id = fk("user_entitlements.id", index=False)
    expires_at = ts()
    created_at = created()
