"""Sources, Ingestion & Evidence — 5 tables (ERD page 4)."""

from sqlalchemy import CHAR, Boolean, Integer, LargeBinary, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts, updated


class DataSource(Base):
    __tablename__ = "data_sources"
    code = c(Text, primary_key=True)
    name = c(Text, nullable=False)
    kind = c(e.data_source_kind, nullable=False)
    base_url = c(Text)
    country_codes = c(ARRAY(CHAR(2)), nullable=False, server_default=text("'{}'"))
    is_enabled = c(Boolean, nullable=False, server_default=text("true"))
    config = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = created()
    updated_at = updated()


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id = pk()
    data_source_code = fk("data_sources.code")
    category_id = fk("categories.id", nullable=True)
    trigger = c(e.job_trigger, nullable=False)
    status = c(e.job_status, nullable=False, server_default="queued", index=True)
    params = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    stats = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    error = c(Text)
    triggered_by_user_id = fk("users.id", nullable=True, index=False)
    started_at = ts()
    finished_at = ts()
    created_at = created()


class SourceRecord(Base):
    """Append-only. The raw copy; a repeat of the same payload_sha256 stops ingestion."""

    __tablename__ = "source_records"
    id = pk()
    data_source_code = fk("data_sources.code")
    record_type = c(e.source_record_type, nullable=False)
    external_id = c(Text, nullable=False, index=True)
    payload = c(JSONB)
    payload_storage_key = c(Text)
    payload_sha256 = c(LargeBinary, nullable=False, index=True)
    ingestion_job_id = fk("ingestion_jobs.id", nullable=True)
    fetched_at = ts(nullable=False, now=True)


class EvidenceItem(Base):
    """Append-only. Everything a score or a passport may cite."""

    __tablename__ = "evidence_items"
    id = pk()
    kind = c(e.evidence_kind, nullable=False)
    recall_id = fk("recalls.id", nullable=True)
    certification_check_id = fk("certification_checks.id", nullable=True)
    source_record_id = fk("source_records.id", nullable=True)
    media_asset_id = fk("media_assets.id", nullable=True)
    review_id = fk("reviews.id", nullable=True)
    hazard_flag_id = fk("hazard_flags.id", nullable=True)
    bbox = c(ARRAY(Integer))
    url = c(Text)
    excerpt = c(Text)
    created_at = created()


class ProductTraceability(Base):
    __tablename__ = "product_traceability"
    id = pk()
    product_id = fk("products.id")
    attribute = c(Text, nullable=False)
    value = c(Text, nullable=False)
    evidence_id = fk("evidence_items.id")
    match_method = c(Text, nullable=False)
    confidence = c(Numeric(4, 3))
    created_at = created()
