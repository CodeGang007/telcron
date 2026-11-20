"""The US Consumer Product Safety Commission's recall feed (SaferProducts.gov, public, no key).

`fetch` is the ONLY code that talks to it and is replaced wholesale in tests. `parse` turns one
of its records into the registry's shape and is pure, so its rules have exact answers.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx

from app.core.config import ROOT, get_settings

SOURCE = "cpsc"
URL = "https://www.saferproducts.gov/RestWebServices/Recall"
CORPORATE = {"USA", "US", "INC", "INC.", "LLC", "CORP", "CORP.", "CO", "CO.", "LTD", "LTD.",
             "COMPANY", "CORPORATION", "GROUP", "AMERICA", "NORTH"}
# "model DR-HSH015", "models A12, B-7 and C9", "model numbers 1234 and 5678"
MODEL_LIST = re.compile(r"\bmodels?(?:\s+numbers?)?[:\s]+([^.;()]{2,120})", re.I)
MODEL_TOKEN = re.compile(r"^[A-Z0-9][A-Z0-9\-/]{2,24}$")


@dataclass(frozen=True)
class ParsedProduct:
    name: str
    brand: str | None
    manufacturer: str | None
    image_urls: list[str]
    identifiers: list[tuple[str, str]]  # (recall_identifier_type, value as published)


@dataclass(frozen=True)
class ParsedRecall:
    external_id: str
    recall_number: str | None
    title: str
    description: str | None
    hazard: str | None
    remedy: str | None
    units_affected: str | None
    recall_date: date | None
    url: str | None
    products: list[ParsedProduct] = field(default_factory=list)


async def fetch(start: date, end: date) -> list[dict]:
    recorded = get_settings().cpsc_fixture
    if recorded:
        path = Path(recorded) if Path(recorded).is_absolute() else ROOT / recorded
        return json.loads(path.read_text())
    headers = {"User-Agent": "telcron-registry/0.1"}
    async with httpx.AsyncClient(timeout=60, headers=headers) as http:
        response = await http.get(URL, params={
            "format": "json", "RecallDateStart": start.isoformat(),
            "RecallDateEnd": end.isoformat()})
        response.raise_for_status()
        return response.json()


def _joined(items: list[dict] | None, key: str = "Name") -> str | None:
    text = " ".join(str(i.get(key) or "").strip() for i in items or []).strip()
    return text or None


def brand_from_title(title: str) -> str | None:
    """CPSC titles read "<Company> Recalls <product> Due to ...". The feed has no brand field."""
    if " Recalls " not in title:
        return None
    words = title.split(" Recalls ", 1)[0].split()
    while words and words[-1].upper().strip(",") in CORPORATE:
        words.pop()
    return " ".join(words).strip(",") or None


def models_in(text: str) -> list[str]:
    """Model numbers named in running text. Only tokens with a digit count: words are not models."""
    found: list[str] = []
    for chunk in MODEL_LIST.findall(text or ""):
        for token in re.split(r"[,\s]+|\band\b|\bor\b", chunk):
            token = token.strip(" :").upper()
            if MODEL_TOKEN.match(token) and any(ch.isdigit() for ch in token) \
                    and token not in found:
                found.append(token)
    return found


def parse(record: dict) -> ParsedRecall:
    title = (record.get("Title") or "").strip()
    brand = brand_from_title(title)
    makers = record.get("Manufacturers") or record.get("Importers") or \
        record.get("Distributors") or []
    manufacturer = (makers[0].get("Name") or "").split(", of ")[0].strip() if makers else None
    images = [i["URL"] for i in record.get("Images") or [] if i.get("URL")]
    upcs = [u["UPC"] for u in record.get("ProductUPCs") or [] if u.get("UPC")]
    entries = record.get("Products") or []
    products = []
    for entry in entries:
        name = (entry.get("Name") or title).strip()
        models = models_in(f"{entry.get('Model') or ''} {name}")
        if entry.get("Model") and not models:
            models = [entry["Model"].strip()]
        if not models:
            models = models_in(record.get("Description") or "")
        identifiers = [("model_number", m) for m in models] + [("gtin", u) for u in upcs]
        products.append(ParsedProduct(name[:500], brand, manufacturer or None, images,
                                      identifiers))
    day = (record.get("RecallDate") or "")[:10]
    return ParsedRecall(
        external_id=str(record["RecallID"]),
        recall_number=record.get("RecallNumber") or None,
        title=title, description=record.get("Description") or None,
        hazard=_joined(record.get("Hazards")), remedy=_joined(record.get("Remedies")),
        units_affected=_joined(entries, "NumberOfUnits"),
        recall_date=date.fromisoformat(day) if day else None,
        url=record.get("URL") or None, products=products)
