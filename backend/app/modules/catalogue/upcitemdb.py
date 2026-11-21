"""UPCitemdb's free lookup (100 requests a day, no key). The ONLY code that talks to it; replaced
wholesale in tests. Returns the first item for a barcode, or None when the database does not know it."""

from typing import Any

import httpx

URL = "https://api.upcitemdb.com/prod/trial/lookup"


class LookupUnavailable(Exception):
    """The service refused or failed (its daily limit, an outage). Not the same as 'unknown'."""


async def lookup(gtin: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "telcron-registry/0.1"}) as http:
            response = await http.get(URL, params={"upc": gtin.lstrip("0").zfill(12)})
    except httpx.HTTPError as exc:
        raise LookupUnavailable(str(exc)) from exc
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise LookupUnavailable(f"HTTP {response.status_code}")
    items = response.json().get("items") or []
    return items[0] if items else None
