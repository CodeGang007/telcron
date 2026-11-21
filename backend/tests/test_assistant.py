"""Vectors, semantic search and the product assistant (WO-015)."""

import hashlib
import json
import math
import re
import uuid

import pytest
from helpers import API, verified_user
from sqlalchemy import select

from app.core.config import get_settings
from app.models import ChatMessage, ProductEmbedding, ProductTraceability
from app.modules.assistant import chat, embedder
from app.modules.assistant.index import index_product
from app.modules.research import web
from app.modules.screening import llm


async def fake_embed(texts, kind="passage"):
    """Words hashed into 384 buckets: texts sharing words are close. Deterministic, no model."""
    out = []
    for t in texts:
        v = [0.0] * 384
        for w in re.findall(r"[a-z0-9]+", t.lower()):
            v[int(hashlib.sha256(w.encode()).hexdigest(), 16) % 384] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


@pytest.fixture
def vectors(monkeypatch):
    monkeypatch.setattr(get_settings(), "embed_url", "http://embedder.test")
    monkeypatch.setattr(embedder, "embed", fake_embed)


async def _product(client, member, name, brand, description=None):
    made = (await client.post(f"{API}/identify/confirm", headers=member, json={
        "name": name, "brand": brand, "category": "appliances"})).json()
    return made


async def test_products_are_found_by_meaning_too(client, db, vectors, monkeypatch):
    from app.modules.catalogue import service as catalogue
    monkeypatch.setattr(catalogue, "CLOSE", 0.6)  # the word-hash stand-in is looser than the model
    _, _, member = await verified_user(client)
    tag = uuid.uuid4().hex[:6]
    made = await _product(client, member, f"Quorra Q{tag}", "Quorra")
    product = (await client.get(f"{API}/products/{made['slug']}")).json()
    # What research found becomes part of what the product's vector is about.
    from app.models import EvidenceItem
    ev = EvidenceItem(kind="web_document", url="https://example.org/q",
                      excerpt="Quorra pedestal fan overheating motor")
    db.add(ev)
    await db.flush()
    db.add(ProductTraceability(product_id=uuid.UUID(product["id"]), attribute="web_complaint",
                               value="pedestal fan overheating motor", evidence_id=ev.id,
                               match_method="web_search+llm"))
    await db.flush()
    done = await index_product(db, uuid.UUID(product["id"]))
    await db.commit()
    assert done == {"product": 1, "evidence": 1}
    assert await index_product(db, uuid.UUID(product["id"])) == {"product": 0, "evidence": 0}
    stored = await db.scalar(select(ProductEmbedding.model_code).where(
        ProductEmbedding.product_id == uuid.UUID(product["id"])))
    assert stored == "bge-small-en-v1.5:384"
    # Nothing in the name says "pedestal fan overheating": only the vector can find it.
    found = (await client.get(f"{API}/products", params={"q": "pedestal fan overheating"})).json()
    assert made["slug"] in [p["slug"] for p in found]


def answers(body):
    seen = {}

    async def complete(messages):
        seen["messages"] = messages
        return {"model": "test-model", "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "choices": [{"message": {"content": json.dumps(body)}}]}
    return complete, seen


async def test_the_assistant_answers_from_cited_evidence_and_remembers(client, db, vectors,
                                                                        monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_api_key", "test")
    _, _, member = await verified_user(client)
    made = await _product(client, member, f"Norda Kettle K{uuid.uuid4().hex[:4]}", "Norda")
    pid = uuid.UUID((await client.get(f"{API}/products/{made['slug']}")).json()["id"])
    from app.models import EvidenceItem
    ev = EvidenceItem(kind="web_document", url="https://www.gov.uk/norda-kettle",
                      excerpt="UK OPSS: Norda kettle recalled because the lid can open and "
                              "scald users with boiling water")
    db.add(ev)
    await db.flush()
    db.add(ProductTraceability(product_id=pid, attribute="web_recall", value="Norda kettle recall",
                               evidence_id=ev.id, match_method="uk_opss+llm"))
    await db.commit()

    complete, seen = answers({"answer": "Yes. The Norda kettle was recalled because the lid can "
                              "open and scald users with boiling water.", "citations": ["E1", "E9"],
                              "answerable": True})
    monkeypatch.setattr(llm, "complete", complete)
    first = (await client.post(f"{API}/products/{made['slug']}/assistant", headers=member,
                               json={"message": "Has this kettle been recalled?"})).json()
    assert first["grounded"] is True and "recalled" in first["answer"]
    assert [c["url"] for c in first["citations"]] == ["https://www.gov.uk/norda-kettle"]  # E9 dropped
    assert "E1 [web_document]" in seen["messages"][-1]["content"]

    # A claim the evidence does not make is replaced, not shown.
    complete, seen = answers({"answer": "It also contains asbestos and was banned in France.",
                              "citations": ["E1"], "answerable": True})
    monkeypatch.setattr(llm, "complete", complete)
    second = (await client.post(f"{API}/products/{made['slug']}/assistant", headers=member, json={
        "message": "Anything else?", "thread_id": first["thread_id"]})).json()
    assert second["answer"] == chat.UNKNOWN and second["citations"] == []
    # Memory: the earlier turns went with the new question.
    assert [m["role"] for m in seen["messages"][1:3]] == ["user", "assistant"]

    history = (await client.get(f"{API}/products/{made['slug']}/assistant", headers=member)).json()
    assert history["thread_id"] == first["thread_id"] and len(history["messages"]) == 4
    rows = (await db.execute(select(ChatMessage).where(
        ChatMessage.thread_id == uuid.UUID(first["thread_id"])))).scalars().all()
    assert {r.prompt_version for r in rows if r.role == "assistant"} == {chat.PROMPT_VERSION}

    # Another member cannot continue this conversation; a visitor cannot ask at all.
    _, _, other = await verified_user(client, "Other")
    stolen = await client.post(f"{API}/products/{made['slug']}/assistant", headers=other, json={
        "message": "Hello there", "thread_id": first["thread_id"]})
    assert stolen.status_code == 404
    assert (await client.post(f"{API}/products/{made['slug']}/assistant",
                              json={"message": "hi there"})).status_code == 401


def test_grounding_is_checked_against_the_cited_text():
    source = ["UK OPSS: kettle recalled because the lid can open and scald users"]
    assert chat.grounded("The kettle was recalled: the lid can open and scald users.", source, "")
    assert not chat.grounded("It contains asbestos and was banned in France.", source, "")
    assert web.grounded("kettle recalled lid", web.Hit("t", "https://x", source[0]))


async def test_alternatives_are_verified_and_at_least_as_safe(client, db, vectors):
    _, _, member = await verified_user(client)
    made = (await client.post(f"{API}/identify/confirm", headers=member, json={
        "name": f"Whirlo Blender W{uuid.uuid4().hex[:4]}", "brand": "Whirlo",
        "category": "blenders"})).json()
    found = (await client.get(f"{API}/products/{made['slug']}/alternatives")).json()
    assert found["items"], "the demo catalogue has verified blenders"
    for item in found["items"]:
        assert item["slug"] != made["slug"] and item["status_badge"] == "verified"
        assert item["trust_score"] >= found["trust_floor"]
    # With vectors, closeness in meaning decides the order.
    for slug in [made["slug"]] + [i["slug"] for i in found["items"]]:
        pid = uuid.UUID((await client.get(f"{API}/products/{slug}")).json()["id"])
        await index_product(db, pid)
    await db.commit()
    by_meaning = (await client.get(f"{API}/products/{made['slug']}/alternatives")).json()
    assert all(i["status_badge"] == "verified" for i in by_meaning["items"])


async def test_alternatives_are_the_same_kind_and_never_demo_products(client, db, vectors):
    from sqlalchemy import text
    _, _, member = await verified_user(client)
    console = (await client.post(f"{API}/identify/confirm", headers=member, json={
        "name": f"PlayBox Console P{uuid.uuid4().hex[:4]}", "brand": "PlayBox",
        "category": "electronics"})).json()
    found = (await client.get(f"{API}/products/{console['slug']}/alternatives")).json()
    detail = (await client.get(f"{API}/products/{console['slug']}")).json()
    assert all(i["category"] == detail["category"] for i in found["items"])
    blender = (await client.post(f"{API}/identify/confirm", headers=member, json={
        "name": f"Whirlo Blender W{uuid.uuid4().hex[:4]}", "brand": "Whirlo",
        "category": "blenders"})).json()
    await db.execute(text("""UPDATE products SET specifications = specifications || '{"demo": true}'
                             WHERE public_slug = 'aquablend-900'"""))
    await db.commit()
    items = (await client.get(f"{API}/products/{blender['slug']}/alternatives")).json()["items"]
    assert "aquablend-900" not in [i["slug"] for i in items] and not any(i["demo"] for i in items)
    await db.execute(text("""UPDATE products SET specifications = specifications - 'demo'
                             WHERE public_slug = 'aquablend-900'"""))
    await db.commit()
