"""WO-001: a review that pushes a product over the hazard alert threshold reaches the people who keep
it in their wallet, once, and nobody else.

Added by qa-test-engineer under WO-017: until now only the recall path to an alert was tested.
"""

import uuid
from decimal import Decimal

from helpers import API, verified_user
from sqlalchemy import select

from app.models import OutboxEvent
from app.modules.screening import service as screening_service
from app.modules.screening.scorer import DimensionResult
from app.workers.handlers import alerts, screening


class EveryReviewIsDangerous:
    """Stands in for the model: every dimension scores 95, citing the reviews it was given. The
    stub's keyword weights cannot reach the threshold from one review, a real model can."""

    model_code = "test-threshold"
    prompt_version = "n/a"

    async def score(self, product_text, dimensions, evidence):
        reviews = [ev.id for ev in evidence if ev.kind == "review"]
        return [DimensionResult(d.code, Decimal(95) if reviews else None, "Dangerous.", reviews)
                for d in dimensions]


async def test_a_review_over_the_alert_threshold_alerts_the_wallet_holder_once(
        client, db, monkeypatch):
    _, _, holder = await verified_user(client, "Holder")
    _, _, bystander = await verified_user(client, "Bystander")
    _, _, reviewer = await verified_user(client, "Reviewer")
    name = f"Threshold Kettle {uuid.uuid4().hex[:6]}"
    added = await client.post(f"{API}/identify/confirm", headers=holder,
                              json={"name": name, "category": "household"})
    assert added.status_code == 200, added.text
    slug = added.json()["slug"]
    assert (await client.post(f"{API}/wallet/items", headers=holder,
                              json={"product_id": slug})).status_code == 201
    before = (await client.get(f"{API}/products/{slug}/passport")).json()

    monkeypatch.setattr(screening_service, "get_scorer", lambda: EveryReviewIsDangerous())
    r = await client.post(f"{API}/products/{slug}/reviews", headers=reviewer, json={
        "rating": 1, "title": "Caught fire", "body": "It caught fire on the counter."})
    assert r.status_code == 201, r.text
    event = (await db.execute(select(OutboxEvent).where(
        OutboxEvent.event_type == "ReviewSubmitted",
        OutboxEvent.payload["product_id"].astext == before["product_id"]))).scalar_one()
    await screening.handle("ReviewSubmitted", event.payload)

    after = (await client.get(f"{API}/products/{slug}/passport")).json()
    assert after["version"] == before["version"] + 1

    raised = (await db.execute(select(OutboxEvent).where(
        OutboxEvent.event_type == "RiskEventRaised",
        OutboxEvent.payload["product_id"].astext == before["product_id"]))).scalars().all()
    assert len(raised) == 1
    await alerts.handle("RiskEventRaised", raised[0].payload)
    await alerts.handle("RiskEventRaised", raised[0].payload)  # delivered twice, alerted once
    got = (await client.get(f"{API}/alerts", headers=holder)).json()
    assert [(a["event_type"], a["product_slug"]) for a in got] == [("hazard_threshold", slug)]
    assert (await client.get(f"{API}/alerts", headers=bystander)).json() == []
