"""The Open Food / Beauty / Products Facts databases (open data, worldwide, no key). The ONLY code that
talks to them; replaced wholesale in tests. Returns the first database's item for a barcode in the
same shape as UPCitemdb's, or None when none of them knows it."""

from typing import Any

import httpx

DATABASES = ("world.openfoodfacts.org", "world.openbeautyfacts.org", "world.openproductsfacts.org")
FIELDS = "product_name,brands,categories,generic_name,quantity"
CATEGORY_HINT = {"world.openfoodfacts.org": "Food", "world.openbeautyfacts.org": "Household beauty",
                 "world.openproductsfacts.org": "Household"}


class LookupUnavailable(Exception):
    pass


async def lookup(gtin: str) -> dict[str, Any] | None:
    code = gtin.lstrip("0").zfill(13) if len(gtin.lstrip("0")) <= 13 else gtin
    failures = 0
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "telcron-registry/0.1"}) as http:
        for host in DATABASES:
            try:
                response = await http.get(f"https://{host}/api/v2/product/{code}.json",
                                          params={"fields": FIELDS})
                body = response.json() if response.status_code in (200, 404) else None
            except (httpx.HTTPError, ValueError):
                failures += 1
                continue
            if body is None:
                failures += 1
                continue
            product = body.get("product") or {}
            name = (product.get("product_name") or product.get("generic_name") or "").strip()
            if body.get("status") == 1 and name:
                brand = (product.get("brands") or "").split(",")[0].strip() or None
                if product.get("quantity"):
                    name = f"{name} {product['quantity']}"
                return {"title": name, "brand": brand, "model": None,
                        "category": f"{CATEGORY_HINT[host]} {product.get('categories') or ''}",
                        "description": None, "source": "openfacts"}
    if failures == len(DATABASES):
        raise LookupUnavailable("no Open Facts database answered")
    return None
