"""WO-017 QA: a hazard score whose citation is not among the evidence offered is insufficient_data.

The rule lives in `screening/service.py` (step 3), independently of what any scorer returns; before
this test nothing failed when that line was weakened.
"""

from decimal import Decimal

from helpers import product_id
from sqlalchemy import select

from app.core.redis import get_redis
from app.models import HazardAssessment, HazardDimensionScore, HazardScoreCitation
from app.modules.screening.scorer import DimensionResult
from app.modules.screening.service import screen_product


class InventsCitations:
    """A scorer that scores every dimension and cites evidence that was never offered."""

    model_code = "qa-invents-citations"
    prompt_version = "qa"

    async def score(self, product_text, dimensions, evidence):
        return [DimensionResult(d.code, Decimal(80), "Made up.",
                                ["00000000-0000-0000-0000-000000000000"]) for d in dimensions]


async def test_a_score_citing_evidence_that_was_not_offered_is_insufficient_data(db):
    pid = await product_id(db, "voltpro-65w-charger")
    await screen_product(db, pid, "rescreen", scorer=InventsCitations())
    await db.commit()
    await (await get_redis()).delete(f"telcron:passport:{pid}")  # as the Worker does
    assessment = (await db.execute(
        select(HazardAssessment).where(HazardAssessment.product_id == pid,
                                       HazardAssessment.model_code == "qa-invents-citations")
        .order_by(HazardAssessment.created_at.desc()).limit(1))).scalar_one()
    rows = (await db.execute(select(HazardDimensionScore).where(
        HazardDimensionScore.assessment_id == assessment.id))).scalars().all()
    assert rows and {(r.status, r.score) for r in rows} == {("insufficient_data", None)}
    assert assessment.total_score is None and assessment.has_insufficient_data
    cites = (await db.execute(select(HazardScoreCitation).where(
        HazardScoreCitation.assessment_id == assessment.id))).scalars().all()
    assert cites == []
