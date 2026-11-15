"""Media & AI Recognition — 6 tables (ERD page 3)."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, Integer, LargeBinary, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import VECTOR_DIM, Base, created, fk, pk, ts


class MediaBlob(Base):
    """One row per distinct file content; assets point at it."""

    __tablename__ = "media_blobs"
    id = pk()
    sha256 = c(LargeBinary, nullable=False, unique=True)
    kind = c(e.media_kind, nullable=False)
    mime_type = c(Text, nullable=False)
    byte_size = c(BigInteger, nullable=False)
    width = c(Integer)
    height = c(Integer)
    duration_ms = c(Integer)
    storage_key_original = c(Text, nullable=False)
    storage_key_normalized = c(Text)
    perceptual_hash = c(BigInteger, index=True)
    phash_band0 = c(Integer)
    phash_band1 = c(Integer)
    phash_band2 = c(Integer)
    phash_band3 = c(Integer)
    moderation_status = c(e.moderation_status, nullable=False, server_default="pending")
    moderation_labels = c(JSONB)
    created_at = created()


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id = pk()
    blob_id = fk("media_blobs.id")
    owner_user_id = fk("users.id", nullable=True)
    data_source_code = fk("data_sources.code", nullable=True, index=False)
    visibility = c(e.visibility, nullable=False, server_default="public")
    caption = c(Text)
    created_at = created()
    deleted_at = ts()


class MediaAnnotation(Base):
    __tablename__ = "media_annotations"
    id = pk()
    blob_id = fk("media_blobs.id")
    label = c(Text, nullable=False)
    confidence = c(Numeric(4, 3), nullable=False)
    bbox = c(ARRAY(Integer))
    frame_ms = c(Integer)
    product_id = fk("products.id", nullable=True)
    model_code = c(Text, nullable=False)
    created_at = created()


class EmbeddingModel(Base):
    __tablename__ = "embedding_models"
    code = c(Text, primary_key=True)
    modality = c(e.embedding_modality, nullable=False)
    dimensions = c(Integer, nullable=False)
    is_active = c(Boolean, nullable=False, server_default=text("true"))
    created_at = created()


class MediaEmbedding(Base):
    __tablename__ = "media_embeddings"
    blob_id = fk("media_blobs.id", primary_key=True)
    model_code = fk("embedding_models.code", primary_key=True)
    embedding = c(Vector(VECTOR_DIM), nullable=False)
    created_at = created()


class IdentificationRequest(Base):
    __tablename__ = "identification_requests"
    id = pk()
    user_id = fk("users.id", nullable=True)
    input_type = c(e.capture_input, nullable=False)
    media_asset_id = fk("media_assets.id", nullable=True, index=False)
    barcode_value = c(Text)
    text_query = c(Text)
    status = c(e.identification_status, nullable=False, server_default="pending")
    extracted = c(JSONB)
    confidence = c(Numeric(4, 3))
    escalated = c(Boolean, nullable=False, server_default=text("false"))
    fallback_manufacturer = c(Text)
    fallback_model = c(Text)
    resolved_product_id = fk("products.id", nullable=True)
    cache_hit = c(Boolean, nullable=False, server_default=text("false"))
    created_at = created()
    completed_at = ts()
