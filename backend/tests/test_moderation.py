"""The safety team's queue: a decision there pays coins, moves trust, alerts and re-screens."""

import uuid

from helpers import API, me, product_id, staff_user, verified_user
from sqlalchemy import select, text

from app.models import FraudHold, OutboxEvent, ReviewTask, User
from app.modules.rewards.service import _queue_hold_review
from app.workers.handlers import alerts, screening

SLUG = "voltpro-65w-charger"
FLAG = {"dimension_code": "safety.health_safety",
        "description": "The casing melted near the plug and it gave me an electric shock."}


async def task_for(client, staff, description_or_reason: str) -> dict:
    tasks = (await client.get(f"{API}/review-tasks", headers=staff)).json()
    for task in tasks:
        subject = task["subject"]
        if description_or_reason in (subject.get("description"), subject.get("reason"),
                                     subject.get("proposed_value")):
            return task
    raise AssertionError(f"no open task about {description_or_reason!r}")


async def events_for(db, event_type: str, pid) -> list[OutboxEvent]:
    return list((await db.execute(select(OutboxEvent).where(
        OutboxEvent.event_type == event_type,
        OutboxEvent.payload["product_id"].astext == str(pid))
        .order_by(OutboxEvent.created_at))).scalars())


async def test_a_confirmed_flag_pays_alerts_and_becomes_evidence(client, db):
    pid = await product_id(db, SLUG)
    _, _, holder = await verified_user(client, "Holder")
    await client.post(f"{API}/wallet/items", headers=holder, json={"product_id": SLUG})
    _, _, reporter = await verified_user(client, "Reporter")
    _, staff = await staff_user(client, db)
    before = (await client.get(f"{API}/products/{SLUG}/passport")).json()

    r = await client.post(f"{API}/products/{SLUG}/flags", headers=reporter, json=FLAG)
    assert r.status_code == 201 and r.json()["coins_pending"] == 0
    again = await client.post(f"{API}/products/{SLUG}/flags", headers=reporter, json=FLAG)
    assert again.status_code == 409 and again.json()["detail"] == "flag_pending"
    # The queue is the safety team's alone.
    assert (await client.get(f"{API}/review-tasks", headers=reporter)).status_code == 403

    task = await task_for(client, staff, FLAG["description"])
    assert task["task_type"] == "hazard_flag" and task["subject"]["reporter"] == "Reporter"
    r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=staff,
                          json={"decision": "confirm", "note": "Photo matches the description."})
    assert r.status_code == 200 and r.json()["status"] == "resolved"
    closed = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=staff,
                               json={"decision": "reject"})
    assert closed.status_code == 409 and closed.json()["detail"] == "review_task_closed"

    # The reporter: flag confirmed, 25 coins pending, trust up from 10 to 12.
    mine = (await client.get(f"{API}/contributions", headers=reporter)).json()["flags"]
    assert mine[0]["status"] == "confirmed"
    history = (await client.get(f"{API}/coins/history", headers=reporter)).json()
    assert [e["amount"] for e in history if e["rule_code"] == "hazard_flag_confirmed"] == [25]
    assert (await me(client, reporter))["trust_score"] == 12.0

    # The wallet holder is alerted, once.
    raised = await events_for(db, "RiskEventRaised", pid)
    await alerts.handle("RiskEventRaised", raised[-1].payload)
    got = (await client.get(f"{API}/alerts", headers=holder)).json()
    assert [a["event_type"] for a in got] == ["community_flag_confirmed"]

    # The re-screen cites the confirmed flag as evidence.
    confirmed = await events_for(db, "HazardFlagConfirmed", pid)
    await screening.handle("HazardFlagConfirmed", confirmed[-1].payload)
    after = (await client.get(f"{API}/products/{SLUG}/passport")).json()
    assert after["version"] == before["version"] + 1
    health = next(d for d in after["hazard"]["dimensions"] if d["code"] == "safety.health_safety")
    assert "hazard_flag" in {c["kind"] for c in health["citations"]}


async def test_a_rejected_flag_pays_nothing_and_costs_trust(client, db):
    _, _, reporter = await verified_user(client, "Hasty")
    _, staff = await staff_user(client, db)
    flag = {"description": "I do not like the colour of this charger at all, honestly."}
    await client.post(f"{API}/products/{SLUG}/flags", headers=reporter, json=flag)
    task = await task_for(client, staff, flag["description"])
    r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=staff,
                          json={"decision": "reject", "note": "Not a hazard."})
    assert r.status_code == 200
    mine = (await client.get(f"{API}/contributions", headers=reporter)).json()["flags"]
    assert (mine[0]["status"], mine[0]["resolution_note"]) == ("rejected", "Not a hazard.")
    history = (await client.get(f"{API}/coins/history", headers=reporter)).json()
    assert not [e for e in history if e["rule_code"] == "hazard_flag_confirmed"]
    assert (await me(client, reporter))["trust_score"] == 9.0


async def test_staff_cannot_decide_their_own_flag(client, db):
    _, staff = await staff_user(client, db, name="Both Hats")
    flag = {"description": "The cable frays where it meets the plug after light use."}
    await client.post(f"{API}/products/{SLUG}/flags", headers=staff, json=flag)
    task = await task_for(client, staff, flag["description"])
    r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=staff,
                          json={"decision": "confirm"})
    assert r.status_code == 403 and r.json()["detail"] == "own_item"


async def test_an_accepted_correction_changes_the_product_and_pays(client, db):
    slug = "aquablend-900"
    _, _, member = await verified_user(client, "Careful")
    _, staff = await staff_user(client, db)
    fix = {"attribute": "description", "proposed_value": "900 W blender with a 1.5 litre jug."}
    r = await client.post(f"{API}/products/{slug}/fact-reports", headers=member, json=fix)
    assert r.status_code == 201
    spec = {"attribute": "wattage", "proposed_value": "900"}
    assert (await client.post(f"{API}/products/{slug}/fact-reports", headers=member,
                              json=spec)).status_code == 201
    missing = await client.post(f"{API}/products/{slug}/fact-reports", headers=member,
                                json={"attribute": "colour"})
    assert missing.status_code == 422

    for proposed in (fix["proposed_value"], spec["proposed_value"]):
        task = await task_for(client, staff, proposed)
        r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=staff,
                              json={"decision": "confirm"})
        assert r.status_code == 200, r.text
    product = (await client.get(f"{API}/products/{slug}")).json()
    assert product["description"] == fix["proposed_value"]
    assert product["specifications"]["wattage"] == "900"
    # One payment per product for corrections, however many are accepted.
    history = (await client.get(f"{API}/coins/history", headers=member)).json()
    assert [e["amount"] for e in history if e["rule_code"] == "fact_verification"] == [20]
    assert (await me(client, member))["trust_score"] == 12.0
    assert await events_for(db, "ProductCorrected", await product_id(db, slug))


async def hold_coins(client, db, member, reason: str) -> FraudHold:
    """Freeze the member's pending coins under an open hold with a review task, as the rapid-fire
    rule does (reaching 20 earns in 5 minutes through the API would take a page of setup)."""
    user_id = (await me(client, member))["id"]
    hold = FraudHold(user_id=user_id, reason=reason, rule_triggered="rapid_fire")
    db.add(hold)
    await db.flush()
    await db.execute(text("select coin_apply_hold(cast(:h as uuid))"), {"h": hold.id})
    await _queue_hold_review(db, hold.id, user_id)
    await db.commit()
    return hold


async def coins_of(client, headers) -> tuple[int, int, int]:
    coins = (await client.get(f"{API}/coins", headers=headers)).json()
    return coins["confirmed"], coins["pending"], coins["frozen"]


async def test_the_safety_team_releases_a_fraud_hold(client, db):
    _, _, member = await verified_user(client, "Held")
    _, staff = await staff_user(client, db)
    hold = await hold_coins(client, db, member, "Unusually many rewarded actions in 5 minutes")
    coins = (await client.get(f"{API}/coins", headers=member)).json()
    assert (coins["pending"], coins["frozen"]) == (0, 105)

    task = await task_for(client, staff, hold.reason)
    assert task["task_type"] == "fraud_hold" and task["priority"] == 1
    r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=staff,
                          json={"decision": "reject", "note": "A genuine burst of reviews."})
    assert r.status_code == 200
    coins = (await client.get(f"{API}/coins", headers=member)).json()
    assert (coins["confirmed"], coins["frozen"]) == (105, 0)


async def test_a_moderator_cannot_release_their_own_fraud_hold(client, db):
    """DEF-011: the person a fraud hold was applied to never decides it, by any action."""
    _, own = await staff_user(client, db, name="Held Moderator")
    _, colleague = await staff_user(client, db, name="Colleague")
    reason = "Twenty rewarded actions in four minutes (own hold)"
    hold = await hold_coins(client, db, own, reason)
    before = await coins_of(client, own)
    assert before == (0, 0, 105)

    task = await task_for(client, own, reason)
    claim = await client.post(f"{API}/review-tasks/{task['id']}/claim", headers=own)
    assert claim.status_code == 403 and claim.json()["detail"] == "own_item"
    for decision in ("reject", "confirm", "dismiss"):
        r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=own,
                              json={"decision": decision})
        assert r.status_code == 403 and r.json()["detail"] == "own_item", decision
    assert await coins_of(client, own) == before
    await db.refresh(hold)
    assert hold.status == "open"
    assert (await task_for(client, colleague, reason))["status"] == "open"

    # A colleague can still decide it.
    r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=colleague,
                          json={"decision": "reject"})
    assert r.status_code == 200
    assert await coins_of(client, own) == (105, 0, 0)


async def test_staff_cannot_decide_their_own_correction(client, db):
    _, staff = await staff_user(client, db, name="Editor Too")
    fix = {"attribute": "colour_name", "proposed_value": "Slate grey (own correction)"}
    assert (await client.post(f"{API}/products/{SLUG}/fact-reports", headers=staff,
                              json=fix)).status_code == 201
    task = await task_for(client, staff, fix["proposed_value"])
    assert (await client.post(f"{API}/review-tasks/{task['id']}/claim",
                              headers=staff)).status_code == 403
    r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=staff,
                          json={"decision": "confirm"})
    assert r.status_code == 403 and r.json()["detail"] == "own_item"
    product = (await client.get(f"{API}/products/{SLUG}")).json()
    assert product["specifications"].get("colour_name") != fix["proposed_value"]


async def test_dismissing_a_fraud_hold_releases_the_coins(client, db):
    """DEF-012: without a finding of fraud the frozen coins are the member's."""
    _, _, member = await verified_user(client, "Dismissed Hold")
    _, staff = await staff_user(client, db)
    reason = "A burst of rewarded actions (to be dismissed)"
    hold = await hold_coins(client, db, member, reason)
    assert await coins_of(client, member) == (0, 0, 105)
    task = await task_for(client, staff, reason)
    r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=staff,
                          json={"decision": "dismiss"})
    assert r.status_code == 200 and r.json()["status"] == "dismissed"
    assert r.json()["subject"]["status"] == "released"
    assert await coins_of(client, member) == (105, 0, 0)
    await db.refresh(hold)
    assert hold.status == "released" and hold.resolved_at is not None


async def test_dismissing_a_flag_closes_it_without_a_penalty(client, db):
    """DEF-012: a dismissed flag leaves `pending`, so its reporter can flag the product again."""
    _, _, reporter = await verified_user(client, "Dismissed Flag")
    _, staff = await staff_user(client, db)
    flag = {"description": "The plug gets warm after an hour; not sure it is a hazard (dismiss)."}
    assert (await client.post(f"{API}/products/{SLUG}/flags", headers=reporter,
                              json=flag)).status_code == 201
    task = await task_for(client, staff, flag["description"])
    r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=staff,
                          json={"decision": "dismiss"})
    assert r.status_code == 200 and r.json()["status"] == "dismissed"
    mine = (await client.get(f"{API}/contributions", headers=reporter)).json()["flags"]
    assert mine[0]["status"] == "rejected"
    assert (await me(client, reporter))["trust_score"] == 10.0
    history = (await client.get(f"{API}/coins/history", headers=reporter)).json()
    assert not [e for e in history if e["rule_code"] == "hazard_flag_confirmed"]
    again = {"description": "Now the casing is discoloured near the pins as well (dismiss 2)."}
    assert (await client.post(f"{API}/products/{SLUG}/flags", headers=reporter,
                              json=again)).status_code == 201


async def test_dismissing_a_correction_closes_it_without_a_penalty(client, db):
    _, _, member = await verified_user(client, "Dismissed Fix")
    _, staff = await staff_user(client, db)
    fix = {"attribute": "cable_length", "proposed_value": "1.8 m (to be dismissed)"}
    assert (await client.post(f"{API}/products/{SLUG}/fact-reports", headers=member,
                              json=fix)).status_code == 201
    task = await task_for(client, staff, fix["proposed_value"])
    r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=staff,
                          json={"decision": "dismiss"})
    assert r.status_code == 200 and r.json()["subject"]["status"] == "rejected"
    assert (await me(client, member))["trust_score"] == 10.0
    product = (await client.get(f"{API}/products/{SLUG}")).json()
    assert product["specifications"].get("cable_length") != fix["proposed_value"]


async def test_staff_cannot_decide_a_task_they_submitted_of_an_unlisted_type(client, db):
    """S-20: a task type with no known subject owner falls back to whoever submitted the task."""
    email, own = await staff_user(client, db, name="Content Reporter")
    _, colleague = await staff_user(client, db, name="Colleague Two")
    submitter = (await db.execute(select(User.id).where(User.email == email))).scalar_one()
    # No route opens a `content_report` task yet, so the row is inserted as one would be.
    task = ReviewTask(task_type="content_report", subject_type="review",
                      subject_id=uuid.uuid4(), submitted_by_user_id=submitter)
    db.add(task)
    await db.commit()

    claim = await client.post(f"{API}/review-tasks/{task.id}/claim", headers=own)
    assert claim.status_code == 403 and claim.json()["detail"] == "own_item"
    for decision in ("reject", "confirm", "dismiss"):
        r = await client.post(f"{API}/review-tasks/{task.id}/resolve", headers=own,
                              json={"decision": decision})
        assert r.status_code == 403 and r.json()["detail"] == "own_item", decision

    r = await client.post(f"{API}/review-tasks/{task.id}/resolve", headers=colleague,
                          json={"decision": "dismiss"})
    assert r.status_code == 200 and r.json()["status"] == "dismissed"


async def test_the_queue_marks_a_reviewers_own_items_as_mine(client, db):
    """DEF-101: the queue says which tasks are the viewer's own, so it offers them no decision."""
    _, own = await staff_user(client, db, name="Own Items")
    _, colleague = await staff_user(client, db, name="Colleague Three")
    flag = {"description": "The plug sparks when it is pushed into the socket (own flag)."}
    assert (await client.post(f"{API}/products/{SLUG}/flags", headers=own, json=flag)
            ).status_code == 201
    reason = "Twenty rewarded actions in three minutes (own hold, mine flag)"
    await hold_coins(client, db, own, reason)

    for text_ in (flag["description"], reason):
        assert (await task_for(client, own, text_))["mine"] is True, text_
        assert (await task_for(client, colleague, text_))["mine"] is False, text_

    # Claim and resolve describe the task to the colleague who decides it: not theirs.
    task = await task_for(client, colleague, reason)
    claim = await client.post(f"{API}/review-tasks/{task['id']}/claim", headers=colleague)
    assert claim.status_code == 200 and claim.json()["mine"] is False
    r = await client.post(f"{API}/review-tasks/{task['id']}/resolve", headers=colleague,
                          json={"decision": "reject"})
    assert r.status_code == 200 and r.json()["mine"] is False
