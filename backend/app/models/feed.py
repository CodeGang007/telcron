"""Commerce Feed & Personalisation — 5 tables (ERD page 9). Phase two, except search_queries."""

from sqlalchemy import CHAR, REAL, Boolean, Numeric, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts


class Topic(Base):
    __tablename__ = "topics"
    code = c(Text, primary_key=True)
    name = c(Text, nullable=False)
    sort_order = c(SmallInteger, nullable=False, server_default="0")


class FeedItem(Base):
    __tablename__ = "feed_items"
    id = pk()
    item_type = c(e.feed_item_type, nullable=False)
    data_source_code = fk("data_sources.code", index=False)
    external_id = c(Text)
    source_record_id = fk("source_records.id", nullable=True, index=False)
    media_asset_id = fk("media_assets.id", nullable=True, index=False)
    post_id = fk("posts.id", nullable=True, index=False)
    recall_id = fk("recalls.id", nullable=True, index=False)
    product_id = fk("products.id", nullable=True)
    category_id = fk("categories.id", nullable=True)
    country_code = c(CHAR(2))
    title = c(Text)
    ai_label = c(Text)
    ai_confidence = c(Numeric(4, 3))
    trending_score = c(REAL, nullable=False, server_default="0")
    is_public = c(Boolean, nullable=False, server_default=text("true"))
    published_at = ts(nullable=False, now=True)
    created_at = created()


class FeedItemTopic(Base):
    __tablename__ = "feed_item_topics"
    feed_item_id = fk("feed_items.id", primary_key=True)
    topic_code = fk("topics.code", primary_key=True)
    confidence = c(Numeric(4, 3))


class SearchQuery(Base):
    """Append-only. Logged in phase one. The ERD marks user_id required and FK to users;
    anonymous search (F1) needs it nullable — DEF-001."""

    __tablename__ = "search_queries"
    id = pk()
    user_id = fk("users.id", nullable=True)
    query_text = c(Text)
    query_media_id = fk("media_assets.id", nullable=True, index=False)
    clicked_product_id = fk("products.id", nullable=True, index=False)
    created_at = created()


class FeedInteraction(Base):
    """Append-only. No foreign keys in the ERD (high-volume log)."""

    __tablename__ = "feed_interactions"
    id = pk()
    user_id = c(UUID(as_uuid=True), nullable=False, index=True)
    feed_item_id = c(UUID(as_uuid=True), nullable=False, index=True)
    action = c(e.feed_action, nullable=False)
    created_at = created()
