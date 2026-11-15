"""Identity & Access — 7 tables (ERD page 2)."""

from sqlalchemy import CHAR, Boolean, LargeBinary, Numeric, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import CITEXT, INET, UUID
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts, updated


class User(Base):
    __tablename__ = "users"
    id = pk()
    email = c(CITEXT, nullable=False, unique=True)
    email_verified_at = ts()
    phone_e164 = c(Text)
    phone_verified_at = ts()
    password_hash = c(Text)
    password_changed_at = ts()
    display_name = c(Text, nullable=False)
    avatar_media_id = fk("media_assets.id", nullable=True, index=False, use_alter=True)
    country_code = c(CHAR(2))
    subdivision_code = c(Text)
    locale = c(Text, nullable=False, server_default="en")
    time_zone = c(Text, nullable=False, server_default="UTC")
    status = c(e.user_status, nullable=False, server_default="active")
    role = c(e.user_role, nullable=False, server_default="user")
    verification_level = c(SmallInteger, nullable=False, server_default="0")
    trust_score = c(Numeric(5, 2), nullable=False, server_default="0")
    referral_code = c(Text, nullable=False, unique=True)
    failed_login_count = c(SmallInteger, nullable=False, server_default="0")
    locked_until = ts()
    last_login_at = ts()
    created_at = created()
    updated_at = updated()
    deleted_at = ts()


class UserIdentity(Base):
    __tablename__ = "user_identities"
    id = pk()
    user_id = fk("users.id")
    provider = c(e.auth_provider, nullable=False)
    provider_subject = c(Text, nullable=False)
    provider_email = c(CITEXT)
    provider_email_verified = c(Boolean, nullable=False, server_default=text("false"))
    last_used_at = ts()
    created_at = created()


class Session(Base):
    __tablename__ = "sessions"
    id = pk()
    user_id = fk("users.id")
    family_id = c(UUID(as_uuid=True), nullable=False, index=True)
    refresh_token_hash = c(LargeBinary, nullable=False, unique=True)
    family_expires_at = ts(nullable=False)
    expires_at = ts(nullable=False)
    last_active_at = ts(nullable=False, now=True)
    rotated_at = ts()
    replaced_by_session_id = fk("sessions.id", nullable=True, index=False)
    ip_address = c(INET)
    user_agent = c(Text)
    revoked_at = ts()
    revoke_reason = c(Text)
    created_at = created()


class VerificationToken(Base):
    __tablename__ = "verification_tokens"
    id = pk()
    user_id = fk("users.id")
    purpose = c(e.token_purpose, nullable=False)
    target = c(Text, nullable=False)
    token_hash = c(LargeBinary, nullable=False, unique=True)
    attempt_count = c(SmallInteger, nullable=False, server_default="0")
    expires_at = ts(nullable=False)
    consumed_at = ts()
    created_at = created()


class AuthEvent(Base):
    """Append-only."""

    __tablename__ = "auth_events"
    id = pk()
    user_id = c(UUID(as_uuid=True), index=True)
    event_type = c(e.auth_event_type, nullable=False)
    email_attempted = c(CITEXT)
    provider = c(e.auth_provider)
    failure_reason = c(Text)
    ip_address = c(INET)
    user_agent = c(Text)
    created_at = created()


class IdentityVerification(Base):
    __tablename__ = "identity_verifications"
    id = pk()
    user_id = fk("users.id")
    document_type = c(Text)
    document_country = c(CHAR(2))
    status = c(e.identity_check_status, nullable=False, server_default="pending")
    ocr_succeeded = c(Boolean)
    face_match_score = c(Numeric(5, 4))
    failure_reason = c(Text)
    provider = c(Text)
    created_at = created()
    completed_at = ts()


class TrustScoreEvent(Base):
    """Append-only."""

    __tablename__ = "trust_score_events"
    id = pk()
    user_id = fk("users.id")
    delta = c(Numeric(5, 2), nullable=False)
    score_after = c(Numeric(5, 2), nullable=False)
    reason_code = c(Text, nullable=False)
    reference_type = c(Text)
    reference_id = c(UUID(as_uuid=True))
    created_at = created()
