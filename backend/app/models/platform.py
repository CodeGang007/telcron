"""Platform, Audit & Operations — 6 tables (ERD page 10)."""

from sqlalchemy import Boolean, Index, Integer, Numeric, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts, updated


class AppSetting(Base):
    __tablename__ = "app_settings"
    key = c(Text, primary_key=True)
    value = c(JSONB, nullable=False)
    description = c(Text)
    updated_at = updated()


class AuditLog(Base):
    """Append-only."""

    __tablename__ = "audit_log"
    id = pk()
    actor_type = c(e.actor_type, nullable=False)
    actor_user_id = c(UUID(as_uuid=True), index=True)
    action = c(Text, nullable=False)
    entity_type = c(Text, nullable=False)
    entity_id = c(UUID(as_uuid=True))
    request_id = c(Text)
    trace_id = c(Text)
    ip_address = c(INET)
    changes = c(JSONB)
    metadata_ = c("metadata", JSONB)
    created_at = created()


class OutboxEvent(Base):
    """Critical events, written in the same transaction as the data they describe."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_unpublished", "created_at",
              postgresql_where=text("published_at IS NULL")),
    )
    id = pk()
    aggregate_type = c(Text, nullable=False)
    aggregate_id = c(UUID(as_uuid=True), nullable=False)
    event_type = c(Text, nullable=False)
    payload = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    published_at = ts()
    attempts = c(SmallInteger, nullable=False, server_default="0")
    created_at = created()


class ReviewTask(Base):
    __tablename__ = "review_tasks"
    id = pk()
    task_type = c(e.review_task_type, nullable=False)
    subject_type = c(Text, nullable=False)
    subject_id = c(UUID(as_uuid=True), nullable=False)
    status = c(e.review_task_status, nullable=False, server_default="open", index=True)
    priority = c(SmallInteger, nullable=False, server_default="0")
    submitted_by_user_id = fk("users.id", nullable=True, index=False)
    payload = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    assigned_to_user_id = fk("users.id", nullable=True, index=False)
    resolution = c(Text)
    resolved_at = ts()
    created_at = created()
    updated_at = updated()


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    code = c(Text, primary_key=True)
    description = c(Text)
    is_enabled = c(Boolean, nullable=False, server_default=text("false"))
    rollout = c(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at = updated()


class AiInvocation(Base):
    """Append-only. Every model call, with tokens, cost and latency."""

    __tablename__ = "ai_invocations"
    id = pk()
    purpose = c(e.ai_purpose, nullable=False)
    model_code = c(Text, nullable=False)
    prompt_version = c(Text)
    user_id = c(UUID(as_uuid=True))
    subject_type = c(Text)
    subject_id = c(UUID(as_uuid=True))
    input_tokens = c(Integer)
    output_tokens = c(Integer)
    cost_usd = c(Numeric(10, 6))
    latency_ms = c(Integer)
    succeeded = c(Boolean, nullable=False)
    error = c(Text)
    created_at = created()
