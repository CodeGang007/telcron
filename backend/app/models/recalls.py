"""Recalls — 5 tables (ERD page 4)."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import CHAR, Date, Index, LargeBinary, Text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import VECTOR_DIM, Base, created, fk, pk, ts, updated


class Recall(Base):
    __tablename__ = "recalls"
    __table_args__ = (Index("ix_recalls_search_tsv", "search_tsv", postgresql_using="gin"),)
    id = pk()
    data_source_code = fk("data_sources.code")
    external_id = c(Text, nullable=False, index=True)
    recall_number = c(Text)
    title = c(Text, nullable=False)
    description = c(Text)
    hazard = c(Text)
    remedy = c(Text)
    classification = c(Text)
    units_affected = c(Text)
    recall_date = c(Date)
    status = c(e.recall_status, nullable=False, server_default="active")
    url = c(Text)
    source_record_id = fk("source_records.id", nullable=True, index=False)
    search_tsv = c(TSVECTOR)
    synced_at = ts(nullable=False, now=True)
    created_at = created()
    updated_at = updated()


class RecallRegion(Base):
    __tablename__ = "recall_regions"
    recall_id = fk("recalls.id", primary_key=True)
    country_code = c(CHAR(2), primary_key=True)
    subdivision_code = c(Text, primary_key=True, server_default="")


class RecallProduct(Base):
    __tablename__ = "recall_products"
    id = pk()
    recall_id = fk("recalls.id")
    product_name = c(Text, nullable=False)
    brand_name = c(Text)
    manufacturer_name = c(Text)
    description = c(Text)
    sold_from = c(Date)
    sold_to = c(Date)
    image_urls = c(ARRAY(Text))


class RecallProductIdentifier(Base):
    __tablename__ = "recall_product_identifiers"
    id = pk()
    recall_product_id = fk("recall_products.id")
    identifier_type = c(e.recall_identifier_type, nullable=False)
    value = c(Text, nullable=False)
    value_normalized = c(Text, nullable=False, index=True)


class RecallEmbedding(Base):
    __tablename__ = "recall_embeddings"
    recall_id = fk("recalls.id", primary_key=True)
    model_code = fk("embedding_models.code", primary_key=True)
    content_sha256 = c(LargeBinary, nullable=False)
    embedding = c(Vector(VECTOR_DIM), nullable=False)
    created_at = created()
