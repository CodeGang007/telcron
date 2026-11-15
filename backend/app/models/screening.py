"""Screening, Hazard & Passport — 10 tables (ERD page 5).

Screenings, matches, assessments, dimension scores, citations, passports and
passport evidence are append-only: a re-screen writes new rows and the product
points to the new passport.
"""

from sqlalchemy import REAL, Boolean, Integer, Numeric, SmallInteger, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, NUMRANGE
from sqlalchemy.orm import mapped_column as c

from . import enums as e
from .base import Base, created, fk, pk, ts


class Screening(Base):
    __tablename__ = "screenings"
    id = pk()
    product_id = fk("products.id")
    run_type = c(e.screening_run_type, nullable=False)
    status = c(e.run_status, nullable=False, server_default="running")
    verdict = c(e.recall_verdict)
    rationale = c(Text)
    candidates_considered = c(SmallInteger)
    corpus_synced_at = ts(nullable=False)
    model_code = c(Text)
    prompt_version = c(Text)
    started_at = ts(nullable=False, now=True)
    completed_at = ts()


class ScreeningMatch(Base):
    __tablename__ = "screening_matches"
    screening_id = fk("screenings.id", primary_key=True)
    recall_id = fk("recalls.id", primary_key=True)
    rank = c(SmallInteger, nullable=False)
    retrieval_score = c(REAL)
    verdict = c(e.candidate_verdict, nullable=False)
    confidence = c(Numeric(4, 3))
    rationale = c(Text)


class ScoringContext(Base):
    __tablename__ = "scoring_contexts"
    code = c(Text, primary_key=True)
    name = c(Text, nullable=False)
    alert_threshold = c(Numeric(5, 2), nullable=False)
    is_active = c(Boolean, nullable=False, server_default=text("true"))


class ScoringBand(Base):
    __tablename__ = "scoring_bands"
    context_code = fk("scoring_contexts.code", primary_key=True)
    label = c(Text, primary_key=True)
    score_range = c(NUMRANGE, nullable=False)
    action = c(Text, nullable=False)


class HazardDimension(Base):
    __tablename__ = "hazard_dimensions"
    code = c(Text, primary_key=True)
    context_code = fk("scoring_contexts.code")
    name = c(Text, nullable=False)
    description = c(Text)
    weight = c(Numeric(4, 2), nullable=False)
    sort_order = c(SmallInteger, nullable=False, server_default="0")
    is_active = c(Boolean, nullable=False, server_default=text("true"))


class HazardAssessment(Base):
    __tablename__ = "hazard_assessments"
    id = pk()
    product_id = fk("products.id")
    context_code = fk("scoring_contexts.code", index=False)
    total_score = c(Numeric(5, 2))
    label = c(Text)
    input_modalities = c(ARRAY(Text), nullable=False)
    has_insufficient_data = c(Boolean, nullable=False, server_default=text("false"))
    model_code = c(Text, nullable=False)
    prompt_version = c(Text)
    created_at = created()


class HazardDimensionScore(Base):
    __tablename__ = "hazard_dimension_scores"
    assessment_id = fk("hazard_assessments.id", primary_key=True)
    dimension_code = fk("hazard_dimensions.code", primary_key=True)
    context_code = c(Text, nullable=False)
    status = c(e.dimension_score_status, nullable=False)
    score = c(Numeric(5, 2))
    weight_applied = c(Numeric(4, 2), nullable=False)
    justification = c(Text)


class HazardScoreCitation(Base):
    __tablename__ = "hazard_score_citations"
    assessment_id = fk("hazard_assessments.id", primary_key=True)
    dimension_code = c(Text, primary_key=True)
    evidence_id = fk("evidence_items.id", primary_key=True)


class Passport(Base):
    __tablename__ = "passports"
    __table_args__ = (UniqueConstraint("product_id", "version"),)
    id = pk()
    product_id = fk("products.id")
    version = c(Integer, nullable=False)
    tier = c(SmallInteger, nullable=False)
    status_badge = c(e.passport_badge, nullable=False)
    trust_score = c(Numeric(5, 2))
    recall_component = c(Numeric(5, 2))
    certification_component = c(Numeric(5, 2))
    hazard_component = c(Numeric(5, 2))
    screening_id = fk("screenings.id", nullable=True, index=False)
    hazard_assessment_id = fk("hazard_assessments.id", nullable=True, index=False)
    formula_version = c(Text, nullable=False)
    verified_at = ts(nullable=False, now=True)


class PassportEvidence(Base):
    __tablename__ = "passport_evidence"
    passport_id = fk("passports.id", primary_key=True)
    evidence_id = fk("evidence_items.id", primary_key=True)
    purpose = c(e.evidence_purpose, nullable=False)
