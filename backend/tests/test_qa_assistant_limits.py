"""WO-017 QA: two WO-015 claims nothing asserted before — the assistant's daily question limit, and
search falling back to names when the embedder is down."""

import json

from helpers import API, verified_user

from app.core.config import get_settings
from app.modules.assistant import chat, embedder
from app.modules.screening import llm


async def test_the_daily_question_limit_is_a_429(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_api_key", "test")

    async def complete(messages):
        body = {"answer": "I can't find that.", "citations": [], "answerable": False}
        return {"choices": [{"message": {"content": json.dumps(body)}}], "usage": {}}
    monkeypatch.setattr(llm, "complete", complete)
    monkeypatch.setattr(chat, "DAILY_QUESTIONS", 1)
    _, _, member = await verified_user(client)
    url = f"{API}/products/aquablend-900/assistant"
    first = await client.post(url, headers=member, json={"message": "Is it waterproof?"})
    assert first.status_code == 200, first.text
    second = await client.post(url, headers=member, json={"message": "Is it dishwasher safe?"})
    assert second.status_code == 429 and second.json()["detail"] == "assistant_quota_reached"


async def test_search_still_answers_by_name_when_the_embedder_is_down(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "embed_url", "http://embedder.test")

    async def down(texts, kind="passage"):
        raise embedder.EmbedderUnavailable("ConnectError: refused")
    monkeypatch.setattr(embedder, "embed", down)
    r = await client.get(f"{API}/products", params={"q": "aquablend"})
    assert r.status_code == 200 and r.json()[0]["slug"] == "aquablend-900"
