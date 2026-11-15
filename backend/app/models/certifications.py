"""Certifications — 3 tables (ERD page 4)."""

from sqlalchemy import Boolean, Date, Text, text
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts, updated


class CertificationScheme(Base):
    __tablename__ = "certification_schemes"
    code = c(Text, primary_key=True)
    name = c(Text, nullable=False)
    data_source_code = fk("data_sources.code", nullable=True, index=False)
    is_checkable = c(Boolean, nullable=False, server_default=text("false"))


class ProductCertification(Base):
    __tablename__ = "product_certifications"
    id = pk()
    product_id = fk("products.id")
    scheme_code = fk("certification_schemes.code")
    certificate_identifier = c(Text, nullable=False)
    holder_name = c(Text)
    current_status = c(e.cert_status, nullable=False, server_default="unknown")
    valid_from = c(Date)
    valid_until = c(Date)
    last_check_id = fk("certification_checks.id", nullable=True, index=False, use_alter=True)
    created_at = created()
    updated_at = updated()


class CertificationCheck(Base):
    """Append-only."""

    __tablename__ = "certification_checks"
    id = pk()
    product_certification_id = fk("product_certifications.id")
    status = c(e.cert_status, nullable=False)
    method = c(e.check_method, nullable=False)
    source_record_id = fk("source_records.id", nullable=True, index=False)
    reviewed_by_user_id = fk("users.id", nullable=True, index=False)
    notes = c(Text)
    checked_at = ts(nullable=False, now=True)
