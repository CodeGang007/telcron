"""Official product-safety registries searched live for one product (public, no keys). The ONLY
code that talks to them; replaced wholesale in tests.

- UK Office for Product Safety and Standards: product safety alerts, reports and recalls (GOV.UK).
- openFDA enforcement reports: food (and drink), drugs (over-the-counter products) and devices.
Their reports come back as search hits for the research model to read: they name the recalling
firm, not always the brand, so a person or the model decides whether one is this product's.
(US CPSC notices are imported as recalls instead, in service.py; Canada, the EU's Safety Gate and
Australia are reached through the regulator-only web search in web.py.)
"""

import httpx

from .web import Hit

UK = "https://www.gov.uk/api/search.json"
FDA = "https://api.fda.gov/{kind}/enforcement.json"
FDA_KINDS = {"food": ("food",), "household": ("drug",), "electronics": ("device",),
             "appliances": ("device",)}


async def _uk(words: str, limit: int) -> list[Hit]:
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.get(UK, params={
            "filter_format": "product_safety_alert_report_recall", "q": words, "count": limit,
            "fields": "title,link,description,public_timestamp"})
    response.raise_for_status()
    return [Hit(title=f"UK OPSS: {r.get('title', '')}"[:300],
                url=f"https://www.gov.uk{r['link']}",
                snippet=f"{r.get('description', '')} ({(r.get('public_timestamp') or '')[:10]})"[:700],
                source="uk_opss")
            for r in response.json().get("results", []) if r.get("link")]


async def _fda(kind: str, words: str, limit: int) -> list[Hit]:
    terms = " AND ".join(f'product_description:"{w}"' for w in words.split()[:4] if w.isalnum())
    if not terms:
        return []
    url = FDA.format(kind=kind)
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.get(url, params={"search": terms, "limit": limit,
                                               "sort": "report_date:desc"})
    if response.status_code == 404:  # openFDA answers "no matches" with a 404
        return []
    response.raise_for_status()
    hits = []
    for r in response.json().get("results", []):
        number = r.get("recall_number") or ""
        hits.append(Hit(
            title=f"FDA {kind} recall {number}: {r.get('recalling_firm', '')}"[:300],
            url=f"{url}?search=recall_number:%22{number}%22",
            snippet=(f"{r.get('status', '')} {r.get('classification', '')} recall "
                     f"({r.get('report_date', '')}). Product: {r.get('product_description', '')}. "
                     f"Reason: {r.get('reason_for_recall', '')}")[:700],
            source="openfda"))
    return hits


def called(category: str | None) -> list[str]:
    """The codes of the registries `search` asks for this category, in the order it asks them."""
    return ["uk_opss"] + [f"openfda_{k}" for k in FDA_KINDS.get(category or "", ())]


async def search(words: str, category: str | None, limit: int = 5) -> tuple[list[Hit], list[str]]:
    """Hits from every registry that covers this kind of product (`called`), and the errors of
    any that failed, each starting with that registry's code (a registry being down is reported,
    not fatal)."""
    hits: list[Hit] = []
    errors: list[str] = []
    calls = [(code, _uk(words, limit) if code == "uk_opss"
              else _fda(code.removeprefix("openfda_"), words, limit)) for code in called(category)]
    for name, call in calls:
        try:
            hits += await call
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            errors.append(f"{name}: {type(exc).__name__}"[:120])
    return hits, errors
