"""DEF-032: a re-screen with missing evidence reuses the product's open "missing evidence" task.

Before the fix every re-screen whose assessment had an unscored dimension added another
`hazard_insufficient_data` task, so the safety team's queue filled with identical cards.
"""

from decimal import Decimal

from helpers import API, product_id, staff_user
from sqlalchemy import select

from app.models import HazardAssessment, Product, ReviewTask
from app.modules.screening.scorer import DimensionResult
from app.modules.screening.service import screen_product

SLUG = "voltpro-65w-charger"


class ScoresNothing:
    """A scorer that gives no score at all, so every dimension lacks evidence."""

    model_code = "qa-scores-nothing"
    prompt_version = "qa"

    async def score(self, product_text, dimensions, evidence):
        return [DimensionResult(d.code, Decimal(50), "No source.", []) for d in dimensions]


async def _open_tasks(db, pid) -> list[tuple]:
    """(id, subject_id, payload) of the product's open missing-evidence tasks, read fresh."""
    db.expire_all()
    return list((await db.execute(select(
        ReviewTask.id, ReviewTask.subject_id, ReviewTask.payload).where(
        ReviewTask.task_type == "hazard_insufficient_data",
        ReviewTask.status.in_(("open", "in_progress")),
        ReviewTask.payload["product_id"].astext == str(pid)))).all())


async def _latest_assessment(db, pid) -> HazardAssessment:
    return (await db.execute(select(HazardAssessment).where(HazardAssessment.product_id == pid)
                             .order_by(HazardAssessment.created_at.desc()).limit(1))).scalar_one()


async def test_a_rescreen_reuses_the_open_missing_evidence_task_for_the_product(client, db):
    pid = await product_id(db, SLUG)
    _, staff = await staff_user(client, db)
    # Close whatever earlier tests left open, through the queue, so this test starts clean.
    for task in await _open_tasks(db, pid):
        r = await client.post(f"{API}/review-tasks/{task[0]}/resolve", headers=staff,
                              json={"decision": "dismiss"})
        assert r.status_code == 200

    await screen_product(db, pid, "rescreen", scorer=ScoresNothing())
    await db.commit()
    first = await _open_tasks(db, pid)
    assert len(first) == 1
    assert first[0][2]["missing_dimensions"]  # the card can say which dimensions

    await screen_product(db, pid, "rescreen", scorer=ScoresNothing())
    await db.commit()
    second = await _open_tasks(db, pid)
    assert [t[0] for t in second] == [first[0][0]]
    # The reused task points at the newest assessment and passport.
    latest = await _latest_assessment(db, pid)
    assert second[0][1] == latest.id
    current = await db.scalar(select(Product.current_passport_id).where(Product.id == pid))
    assert second[0][2]["passport_id"] == str(current)

    # Once resolved, the next re-screen with missing evidence opens a new one.
    r = await client.post(f"{API}/review-tasks/{first[0][0]}/resolve", headers=staff,
                          json={"decision": "dismiss"})
    assert r.status_code == 200
    await screen_product(db, pid, "rescreen", scorer=ScoresNothing())
    await db.commit()
    third = await _open_tasks(db, pid)
    assert len(third) == 1 and third[0][0] != first[0][0]
