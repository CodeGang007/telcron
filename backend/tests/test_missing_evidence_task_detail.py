"""DEF-120 / CT-003 C: a missing-evidence task in the queue says which dimensions lack evidence and
which passport version it is about, so the safety team has something to check."""

import uuid

from helpers import API, product_id, staff_user
from sqlalchemy import select

from app.models import HazardDimension, Passport, Product, ReviewTask

SLUG = "aquablend-900"


async def test_a_missing_evidence_task_names_its_dimensions_and_passport(client, db):
    pid = await product_id(db, SLUG)
    _, staff = await staff_user(client, db)
    passport = await db.scalar(select(Product.current_passport_id).where(Product.id == pid))
    version = await db.scalar(select(Passport.version).where(Passport.id == passport))
    dims = (await db.execute(select(HazardDimension.code, HazardDimension.name)
                             .order_by(HazardDimension.sort_order).limit(2))).all()
    current = ReviewTask(task_type="hazard_insufficient_data", subject_type="hazard_assessment",
                         subject_id=uuid.uuid4(), priority=1,
                         payload={"product_id": str(pid), "passport_id": str(passport),
                                  "missing_dimensions": [d.code for d in dims]})
    # A task written before DEF-032: only the product in its payload.
    legacy = ReviewTask(task_type="hazard_insufficient_data", subject_type="hazard_assessment",
                        subject_id=uuid.uuid4(), priority=1, payload={"product_id": str(pid)})
    db.add_all([current, legacy])
    await db.commit()

    queue = {t["id"]: t for t in
             (await client.get(f"{API}/review-tasks?limit=100", headers=staff)).json()}
    got = queue[str(current.id)]["subject"]
    assert got["missing_dimensions"] == [{"code": d.code, "name": d.name} for d in dims]
    assert got["passport_version"] == version
    assert got["product"]["slug"] == SLUG
    old = queue[str(legacy.id)]["subject"]
    assert old["missing_dimensions"] == [] and old["passport_version"] is None

    # The single-task view (claim, resolve) describes it the same way.
    r = await client.post(f"{API}/review-tasks/{current.id}/claim", headers=staff)
    assert r.status_code == 200 and r.json()["subject"] == got

    # Leave the queue as it was found.
    for task in (current, legacy):
        r = await client.post(f"{API}/review-tasks/{task.id}/resolve", headers=staff,
                              json={"decision": "dismiss"})
        assert r.status_code == 200


async def test_other_task_types_do_not_gain_the_fields(client, db):
    _, staff = await staff_user(client, db)
    for task in (await client.get(f"{API}/review-tasks?limit=100", headers=staff)).json():
        if task["task_type"] != "hazard_insufficient_data":
            assert "missing_dimensions" not in task["subject"]
            assert "passport_version" not in task["subject"]
