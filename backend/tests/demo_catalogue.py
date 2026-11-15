"""Three INVENTED products the tests run against, written through the application's models
and screened by the application, so the mapping and the database's rules are both exercised."""

import hashlib
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.models import (
    Brand,
    Category,
    CertificationCheck,
    Manufacturer,
    Product,
    ProductAlias,
    ProductCertification,
    Recall,
    RecallProduct,
    RecallProductIdentifier,
    RecallRegion,
    Review,
    SourceRecord,
)
from app.modules.screening.service import screen_product

PRODUCTS = [
    # slug, name, brand, model, category, gtin, certificate (scheme, id) | None, ingested reviews
    ("aquablend-900", "AquaBlend 900 Blender", "AquaBlend", "AB-900", "blenders",
     "00850012345678", ("ul", "E123456"),
     [(2, "Lid cracked after a month",
       "The lid cracked after a month and the jug started to leak onto the motor base."),
      (4, "Strong blender",
       "Blends ice easily and is simple to clean. Loud, but that is expected at this power.")]),
    ("voltpro-65w-charger", "VoltPro 65W USB-C Charger", "VoltPro", "VP-65C", "power_adapters",
     "00850098765432", ("fcc", "2AXYZ-VP65C"),
     [(5, "Reliable",
       "Charges my laptop and phone together and stays cool. No issues after six months.")]),
    ("brightbuild-magnet-set", "BrightBuild Magnetic Tiles 60pc", "BrightBuild", "BB-M60",
     "household", "00850055511122", None, []),
]


def normalized(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


async def add_recall(db, *, external_id: str, title: str, hazard: str, product_name: str,
                     brand: str, model: str) -> Recall:
    recall = Recall(data_source_code="cpsc", external_id=external_id, recall_number=external_id,
                    title=title, hazard=hazard, remedy="Stop using it and contact the seller.",
                    recall_date=date(2026, 9, 12), synced_at=datetime.now(UTC),
                    url=f"https://example.invalid/recalls/{external_id}")
    db.add(recall)
    await db.flush()
    db.add(RecallRegion(recall_id=recall.id, country_code="US"))
    recalled = RecallProduct(recall_id=recall.id, product_name=product_name, brand_name=brand)
    db.add(recalled)
    await db.flush()
    db.add(RecallProductIdentifier(recall_product_id=recalled.id, identifier_type="model_number",
                                   value=model, value_normalized=normalized(model)))
    await db.flush()
    return recall


async def make_catalogue(db) -> None:
    categories = {c.code: c.id for c in (await db.execute(select(Category))).scalars()}
    for slug, name, brand_name, model, category, gtin, certificate, reviews in PRODUCTS:
        maker = Manufacturer(name=f"{brand_name} Inc.", normalized_name=f"{brand_name.lower()} inc")
        db.add(maker)
        await db.flush()
        brand = Brand(name=brand_name, normalized_name=brand_name.lower(),
                      manufacturer_id=maker.id)
        db.add(brand)
        await db.flush()
        product = Product(
            category_id=categories[category], brand_id=brand.id, manufacturer_id=maker.id,
            canonical_name=name, model_number=model, model_number_normalized=normalized(model),
            public_slug=slug, description="Invented for the test suite.",
            identification_source="manual", identity_confidence=1)
        db.add(product)
        await db.flush()
        db.add(ProductAlias(product_id=product.id, alias_type="gtin", alias_value=gtin,
                            data_source_code="upcitemdb", confidence=1))
        if certificate:
            held = ProductCertification(product_id=product.id, scheme_code=certificate[0],
                                        certificate_identifier=certificate[1])
            db.add(held)
            await db.flush()
            # A trigger copies the check's status onto the certificate.
            db.add(CertificationCheck(product_certification_id=held.id, status="valid",
                                      method="api"))
        for i, (rating, title, body) in enumerate(reviews):
            raw = SourceRecord(data_source_code="amazon", record_type="review",
                               external_id=f"{slug}-{i}", payload={"title": title, "body": body},
                               payload_sha256=hashlib.sha256(body.encode()).digest())
            db.add(raw)
            await db.flush()
            db.add(Review(product_id=product.id, origin="ingested", data_source_code="amazon",
                          external_id=raw.external_id, source_record_id=raw.id, rating=rating,
                          title=title, body=body))
        if slug == "brightbuild-magnet-set":
            await add_recall(
                db, external_id="TEST-26-001", product_name=name, brand=brand_name, model=model,
                title="BrightBuild Magnetic Tiles recalled: magnets can come loose",
                hazard="Loose high-powered magnets are an ingestion hazard to children.")
        await db.flush()
        await screen_product(db, product.id, "initial")
