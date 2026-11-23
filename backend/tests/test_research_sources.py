"""DEF-115 (CT-003 §B): a research run records which sources it asked and how each went, so the page
never says the web was searched when no search provider is set up.

`answered` = asked and returned (even with nothing found); `failed` = asked and errored;
`not_configured` = no provider set up, nothing was asked. A source not asked is absent.
"""

import uuid

from helpers import API, product_id

from app.core.config import get_settings
from app.models import IngestionJob
from app.modules.ingestion import cpsc
from app.modules.research import registries, service, web

SLUG = "voltpro-65w-charger"  # brand VoltPro, category power_adapters (no openFDA kind)
REAL_WEB_SEARCH = web.search  # conftest replaces it in every test; this is the real client


async def _run(db, pid) -> dict:
    job = IngestionJob(data_source_code=service.SOURCE, trigger="admin",
                       params={"product_id": str(pid)})
    db.add(job)
    await db.commit()
    return await service.run(job.id)


async def test_with_no_search_provider_the_web_is_not_configured_and_not_counted(
        client, db, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "tavily_api_key", None)
    monkeypatch.setattr(s, "llm_api_key", None)
    monkeypatch.setattr(web, "search", REAL_WEB_SEARCH)
    notice = web.Hit("UK OPSS: Product Recall: VoltPro 65W USB-C Charger VP-65C",
                     f"https://www.gov.uk/product-safety-alerts/{uuid.uuid4().hex}",
                     "Product Recall for VoltPro 65W USB-C Charger VP-65C: risk of fire.",
                     "uk_opss")

    async def registry(words, category, limit=5):
        return [notice], []
    monkeypatch.setattr(registries, "search", registry)

    stats = await _run(db, await product_id(db, SLUG))
    assert stats["sources"] == {"cpsc": "answered", "web": "not_configured",
                                "uk_opss": "answered", "reader": "not_configured"}
    assert stats["pages"] == 1  # the registry's notice only: nothing came from the web

    body = (await client.get(f"{API}/products/{SLUG}/research")).json()
    assert body["stats"]["sources"]["web"] == "not_configured"
    assert body["stats"]["errors"] == ["web", "reader"]  # codes only, as before


async def test_a_provider_error_is_failed_and_its_text_stays_private(client, db, monkeypatch):
    async def broken_search(label, category=None):
        raise web.ResearchUnavailable("HTTPStatusError: 429 key sk-secret over quota")

    async def cpsc_down(brand):
        raise RuntimeError("CPSC said 503")

    async def registry_down(words, category, limit=5):
        return [], ["uk_opss: ConnectTimeout"]
    monkeypatch.setattr(web, "search", broken_search)
    monkeypatch.setattr(cpsc, "search", cpsc_down)
    monkeypatch.setattr(registries, "search", registry_down)

    stats = await _run(db, await product_id(db, SLUG))
    # Nothing was left to read, so the reader was not asked.
    assert stats["sources"] == {"cpsc": "failed", "web": "failed", "uk_opss": "failed"}
    assert stats["pages"] == 0

    body = (await client.get(f"{API}/products/{SLUG}/research")).json()
    assert body["stats"]["sources"] == stats["sources"]
    assert "sk-secret" not in str(body) and "503" not in str(body)


async def test_a_registry_that_finds_nothing_has_still_answered(client, db, monkeypatch):
    # conftest's stand-ins: CPSC, the web and the registries all answer with nothing.
    stats = await _run(db, await product_id(db, SLUG))
    assert stats["sources"] == {"cpsc": "answered", "web": "answered", "uk_opss": "answered"}
    assert stats["pages"] == 0 and stats["errors"] == []


def test_registries_report_the_sources_they_ask_for_a_category():
    assert registries.called("power_adapters") == ["uk_opss"]
    assert registries.called("food") == ["uk_opss", "openfda_food"]
    assert registries.called(None) == ["uk_opss"]


def test_public_stats_pass_sources_through_checked():
    public = service._public_stats({
        "errors": ["web: no search provider configured"],
        "sources": {"web": "not_configured", "uk_opss": "answered", "reader": "failed",
                    "Bad Code!": "answered", "cpsc": "sk-secret"}})
    assert public["sources"] == {"web": "not_configured", "uk_opss": "answered",
                                 "reader": "failed"}
    assert public["errors"] == ["web"]
    # A run recorded before CT-003 has no `sources`; none is invented for it.
    assert "sources" not in service._public_stats({"errors": []})
