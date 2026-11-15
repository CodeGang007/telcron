"""Product Catalogue (Registry) — 7 tables (ERD page 3)."""

from sqlalchemy import CHAR, Boolean, Index, Numeric, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts, updated


class Category(Base):
    __tablename__ = "categories"
    id = pk()
    parent_id = fk("categories.id", nullable=True)
    code = c(Text, nullable=False, unique=True)
    name = c(Text, nullable=False)
    is_active = c(Boolean, nullable=False, server_default=text("true"))
    # Search query, fetch size and cadence, images per product, visual hazard signals (doc 6.4).
    config = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = created()
    updated_at = updated()


class Manufacturer(Base):
    __tablename__ = "manufacturers"
    id = pk()
    name = c(Text, nullable=False)
    normalized_name = c(Text, nullable=False, unique=True)
    country_code = c(CHAR(2))
    website_url = c(Text)
    created_at = created()
    updated_at = updated()


class Brand(Base):
    __tablename__ = "brands"
    id = pk()
    name = c(Text, nullable=False)
    normalized_name = c(Text, nullable=False, unique=True)
    manufacturer_id = fk("manufacturers.id", nullable=True)
    created_at = created()
    updated_at = updated()


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_canonical_name_trgm", "canonical_name", postgresql_using="gin",
              postgresql_ops={"canonical_name": "gin_trgm_ops"}),
    )
    id = pk()
    category_id = fk("categories.id")
    brand_id = fk("brands.id", nullable=True)
    manufacturer_id = fk("manufacturers.id", nullable=True)
    canonical_name = c(Text, nullable=False)
    model_number = c(Text)
    model_number_normalized = c(Text, index=True)
    description = c(Text)
    specifications = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = c(e.product_status, nullable=False, server_default="active")
    merged_into_product_id = fk("products.id", nullable=True, index=False)
    identification_source = c(e.identification_source, nullable=False)
    identity_confidence = c(Numeric(4, 3))
    traceability_status = c(e.traceability_status, nullable=False, server_default="pending")
    traceability_checked_at = ts()
    primary_media_id = fk("media_assets.id", nullable=True, index=False, use_alter=True)
    current_passport_id = fk("passports.id", nullable=True, index=False, use_alter=True)
    public_slug = c(Text, nullable=False, unique=True)
    created_by_user_id = fk("users.id", nullable=True, index=False)
    created_at = created()
    updated_at = updated()


class ProductVariant(Base):
    __tablename__ = "product_variants"
    id = pk()
    product_id = fk("products.id")
    name = c(Text, nullable=False)
    attributes = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = created()


class ProductAlias(Base):
    __tablename__ = "product_aliases"
    __table_args__ = (Index("ix_product_aliases_lookup", "alias_type", "alias_value"),)
    id = pk()
    product_id = fk("products.id")
    variant_id = fk("product_variants.id", nullable=True, index=False)
    alias_type = c(e.alias_type, nullable=False)
    namespace = c(Text, nullable=False, server_default="")
    alias_value = c(Text, nullable=False)
    data_source_code = fk("data_sources.code", nullable=True, index=False)
    confidence = c(Numeric(4, 3))
    created_at = created()


class ProductMedia(Base):
    __tablename__ = "product_media"
    product_id = fk("products.id", primary_key=True)
    media_asset_id = fk("media_assets.id", primary_key=True)
    role = c(e.media_role, nullable=False, server_default="gallery")
    sort_order = c(SmallInteger, nullable=False, server_default="0")
    created_at = created()
