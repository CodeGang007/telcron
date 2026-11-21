"""Vectors for semantic search, and the product assistant's conversations (WO-015)."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, LargeBinary, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column as c

from .base import Base, created, fk, pk, ts


class ProductEmbedding(Base):
    __tablename__ = "product_embeddings"
    product_id = fk("products.id", primary_key=True)
    model_code = fk("embedding_models.code", primary_key=True)
    content_sha256 = c(LargeBinary, nullable=False)
    embedding = c(Vector(), nullable=False)
    created_at = created()


class EvidenceEmbedding(Base):
    __tablename__ = "evidence_embeddings"
    evidence_id = fk("evidence_items.id", primary_key=True)
    model_code = fk("embedding_models.code", primary_key=True)
    embedding = c(Vector(), nullable=False)
    created_at = created()


class ChatThread(Base):
    __tablename__ = "chat_threads"
    id = pk()
    user_id = fk("users.id")
    product_id = fk("products.id")
    created_at = created()
    last_message_at = ts(nullable=False, now=True)


class ChatMessage(Base):
    """Append-only (a trigger refuses UPDATE and DELETE)."""

    __tablename__ = "chat_messages"
    id = pk()
    thread_id = fk("chat_threads.id")
    role = c(Text, nullable=False)
    content = c(Text, nullable=False)
    citations = c(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    model_code = c(Text)
    prompt_version = c(Text)
    input_tokens = c(Integer)
    output_tokens = c(Integer)
    created_at = created()
