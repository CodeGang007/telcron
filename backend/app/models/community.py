"""Community & Reviews — 10 tables (ERD page 8)."""

from sqlalchemy import CHAR, Boolean, Integer, SmallInteger, Text, text
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts, updated


class Review(Base):
    __tablename__ = "reviews"
    id = pk()
    product_id = fk("products.id")
    origin = c(e.content_origin, nullable=False, server_default="user")
    author_user_id = fk("users.id", nullable=True)
    data_source_code = fk("data_sources.code", nullable=True, index=False)
    external_id = c(Text)
    source_record_id = fk("source_records.id", nullable=True, index=False)
    rating = c(SmallInteger, nullable=False)
    title = c(Text)
    body = c(Text, nullable=False)
    author_reward_level = c(SmallInteger)
    verified_owner = c(Boolean, nullable=False, server_default=text("false"))
    geohash = c(Text)
    helpful_count = c(Integer, nullable=False, server_default="0")
    status = c(e.content_status, nullable=False, server_default="published")
    created_at = created()
    updated_at = updated()
    deleted_at = ts()


class ReviewMedia(Base):
    __tablename__ = "review_media"
    review_id = fk("reviews.id", primary_key=True)
    media_asset_id = fk("media_assets.id", primary_key=True)
    sort_order = c(SmallInteger, nullable=False, server_default="0")


class ReviewVote(Base):
    __tablename__ = "review_votes"
    review_id = fk("reviews.id", primary_key=True)
    user_id = fk("users.id", primary_key=True)
    created_at = created()


class Post(Base):
    """Phase two."""

    __tablename__ = "posts"
    id = pk()
    author_user_id = fk("users.id")
    product_id = fk("products.id")
    wallet_item_id = fk("wallet_items.id", nullable=True, index=False)
    body = c(Text, nullable=False)
    geohash = c(Text)
    location_name = c(Text)
    country_code = c(CHAR(2))
    status = c(e.content_status, nullable=False, server_default="published")
    comment_count = c(Integer, nullable=False, server_default="0")
    reaction_count = c(Integer, nullable=False, server_default="0")
    created_at = created()
    updated_at = updated()
    deleted_at = ts()


class PostMedia(Base):
    __tablename__ = "post_media"
    post_id = fk("posts.id", primary_key=True)
    media_asset_id = fk("media_assets.id", primary_key=True)
    sort_order = c(SmallInteger, nullable=False, server_default="0")


class Comment(Base):
    """Phase two."""

    __tablename__ = "comments"
    id = pk()
    post_id = fk("posts.id", nullable=True)
    risk_event_id = fk("risk_events.id", nullable=True)
    author_user_id = fk("users.id")
    parent_comment_id = fk("comments.id", nullable=True, index=False)
    body = c(Text, nullable=False)
    status = c(e.content_status, nullable=False, server_default="published")
    created_at = created()
    updated_at = updated()
    deleted_at = ts()


class Reaction(Base):
    """Phase two."""

    __tablename__ = "reactions"
    post_id = fk("posts.id", primary_key=True)
    user_id = fk("users.id", primary_key=True)
    reaction = c(e.reaction_type, nullable=False)
    created_at = created()


class HazardFlag(Base):
    __tablename__ = "hazard_flags"
    id = pk()
    reporter_user_id = fk("users.id")
    product_id = fk("products.id")
    wallet_item_id = fk("wallet_items.id", nullable=True, index=False)
    dimension_code = fk("hazard_dimensions.code", nullable=True, index=False)
    description = c(Text)
    geohash = c(Text)
    status = c(e.flag_status, nullable=False, server_default="pending", index=True)
    matched_recall_id = fk("recalls.id", nullable=True, index=False)
    reviewed_by_user_id = fk("users.id", nullable=True, index=False)
    reviewed_at = ts()
    resolution_note = c(Text)
    created_at = created()


class HazardFlagMedia(Base):
    __tablename__ = "hazard_flag_media"
    hazard_flag_id = fk("hazard_flags.id", primary_key=True)
    media_asset_id = fk("media_assets.id", primary_key=True)


class ProductFactReport(Base):
    __tablename__ = "product_fact_reports"
    id = pk()
    product_id = fk("products.id")
    reporter_user_id = fk("users.id")
    hazard_flag_id = fk("hazard_flags.id", nullable=True, index=False)
    attribute = c(Text, nullable=False)
    current_value = c(Text)
    proposed_value = c(Text)
    is_confirmation = c(Boolean, nullable=False)
    status = c(e.fact_report_status, nullable=False, server_default="pending")
    reviewed_by_user_id = fk("users.id", nullable=True, index=False)
    reviewed_at = ts()
    created_at = created()
