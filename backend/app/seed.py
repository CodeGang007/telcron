"""Reference data and a small demo catalogue. Idempotent: run it as often as you like.

Reference rows (dimensions, bands, earn rules, levels) are the documented values. The demo
products, recall and reviews are INVENTED for local development and are marked `demo`.
"""

import asyncio
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range, insert

from app.core import security
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.events import emit
from app.models import (
    Badge,
    Brand,
    Category,
    CertificationCheck,
    CertificationScheme,
    CoinEarnRule,
    DataSource,
    EmbeddingModel,
    HazardDimension,
    Manufacturer,
    Product,
    ProductAlias,
    ProductCertification,
    Recall,
    RecallProduct,
    RecallProductIdentifier,
    RecallRegion,
    RedemptionItem,
    Review,
    RewardLevel,
    ScoringBand,
    ScoringContext,
    User,
)

CONTEXT = "consumer_product"
DIMENSIONS = [  # technical documentation 7.4
    ("regulatory_flags", "Regulatory flags", "3.0", "Recalls, banned substances, compliance violations"),
    ("health_safety", "Health and safety", "2.5", "Injury, toxic materials, choking risk"),
    ("customer_issues", "Customer issues", "1.5", "One-star rate, repeated complaints"),
    ("fragility_usability", "Fragility and usability", "1.5", "Breakage reports, design flaws"),
    ("environmental_harm", "Environmental harm", "1.0", "Non-recyclable materials, disposal hazards"),
    ("regional_constraints", "Regional constraints", "1.0", "Voltage, import restrictions, regional bans"),
    ("animal_harm", "Animal harm", "0.5", "Toxic to pets, dangerous baits"),
]
BANDS = [("low", 0, 30, "approve"), ("medium", 30, 60, "review_queue"),
         ("high", 60, 101, "block_and_alert")]
EARN_RULES = [  # technical documentation 9.1: code, amount, capped, per-subject, lifetime
    ("reach_level_1", 100, False, None, 1), ("reach_level_2", 500, False, None, 1),
    ("review", 10, True, 1, None), ("photo", 15, True, None, None),
    ("hazard_flag", 25, True, None, None), ("fact_correction", 20, False, None, None),
    ("first_review", 30, False, 1, None), ("daily_login", 5, False, None, None),
]
# Level names between Novice and Master, and every threshold, are placeholders (ADR-004).
LEVELS = [(1, "Novice", 0), (2, "Contributor", 250), (3, "Guardian", 1000), (4, "Expert", 5000),
          (5, "Master", 20000)]


async def upsert(db, model, rows: list[dict], keys: list[str]) -> None:
    for row in rows:
        stmt = insert(model).values(**row)
        update = {k: v for k, v in row.items() if k not in keys}
        stmt = (stmt.on_conflict_do_update(index_elements=keys, set_=update) if update
                else stmt.on_conflict_do_nothing(index_elements=keys))
        await db.execute(stmt)


async def reference(db) -> None:
    await upsert(db, ScoringContext, [{"code": CONTEXT, "name": "Consumer product",
                                       "alert_threshold": 60}], ["code"])
    await upsert(db, ScoringBand, [
        {"context_code": CONTEXT, "label": label, "score_range": Range(lo, hi), "action": action}
        for label, lo, hi, action in BANDS], ["context_code", "label"])
    await upsert(db, HazardDimension, [
        {"code": code, "context_code": CONTEXT, "name": name, "weight": weight,
         "description": desc, "sort_order": i}
        for i, (code, name, weight, desc) in enumerate(DIMENSIONS)], ["code"])
    await upsert(db, CoinEarnRule, [
        {"code": code, "amount": amount, "counts_toward_daily_cap": capped,
         "per_subject_limit": per_subject, "lifetime_limit": lifetime,
         "confirmation_delay": timedelta(minutes=10)}
        for code, amount, capped, per_subject, lifetime in EARN_RULES], ["code"])
    await upsert(db, RewardLevel, [{"level": n, "title": t, "min_lifetime_coins": m}
                                   for n, t, m in LEVELS], ["level"])
    await upsert(db, RedemptionItem, [
        {"code": "hazard_report_pdf", "name": "Full hazard report (PDF)", "cost_coins": 200,
         "fulfilment_type": "hazard_report_pdf"},
        {"code": "extra_watches", "name": "Five extra product watches", "cost_coins": 150,
         "fulfilment_type": "extra_watches", "quantity": 5}], ["code"])
    await upsert(db, Badge, [{"code": "first_review", "name": "First reviewer",
                              "description": "Wrote the first review of a product."}], ["code"])
    await upsert(db, EmbeddingModel, [{"code": "amazon.titan-embed-image-v1",
                                       "modality": "multimodal", "dimensions": 1024}], ["code"])
    await upsert(db, DataSource, [
        {"code": "demo", "name": "Demo data (invented)", "kind": "internal"},
        {"code": "telcron_users", "name": "Telcron contributors", "kind": "user"}], ["code"])
    await upsert(db, CertificationScheme, [
        {"code": "FCC", "name": "FCC Equipment Authorization"},
        {"code": "UL", "name": "UL Listed"}, {"code": "CE", "name": "CE Marking"}], ["code"])
    await upsert(db, Category, [
        {"code": "small_kitchen_appliances", "name": "Small kitchen appliances"},
        {"code": "chargers_power", "name": "Chargers and power"},
        {"code": "toys", "name": "Toys"}], ["code"])


PRODUCTS = [
    # slug, name, brand, model, category, barcode, cert (scheme, id, status) | None, reviews
    ("aquablend-900", "AquaBlend 900 Blender", "AquaBlend", "AB-900", "small_kitchen_appliances",
     "0850012345678", ("UL", "E123456", "valid"),
     [(2, "Lid cracked after a month", "The lid cracked after a month and the jug started to leak onto the motor base."),
      (1, "Overheats", "Motor started to overheat and there was a burning smell and smoke after two minutes of use."),
      (4, "Strong blender", "Blends ice easily and is simple to clean. Loud, but that is expected at this power.")]),
    ("voltpro-65w-charger", "VoltPro 65W USB-C Charger", "VoltPro", "VP-65C", "chargers_power",
     "0850098765432", ("FCC", "2AXYZ-VP65C", "valid"),
     [(5, "Reliable", "Charges my laptop and phone together and stays cool. No issues after six months."),
      (4, "Compact", "Small enough for travel and the folding plug is handy. Cable is not included.")]),
    ("brightbuild-magnet-set", "BrightBuild Magnetic Tiles 60pc", "BrightBuild", "BB-M60", "toys",
     "0850055511122", None, []),
]


async def demo(db) -> None:
    if (await db.execute(select(Product.id).limit(1))).first():
        return
    cats = {c.code: c.id for c in (await db.execute(select(Category))).scalars()}
    for slug, name, brand_name, model, cat, barcode, cert, reviews in PRODUCTS:
        maker = Manufacturer(name=f"{brand_name} Inc.", normalized_name=f"{brand_name.lower()}inc")
        db.add(maker)
        await db.flush()
        brand = Brand(name=brand_name, normalized_name=brand_name.lower(),
                      manufacturer_id=maker.id)
        db.add(brand)
        await db.flush()
        product = Product(
            category_id=cats[cat], brand_id=brand.id, manufacturer_id=maker.id,
            canonical_name=name, model_number=model, public_slug=slug,
            model_number_normalized="".join(ch for ch in model.lower() if ch.isalnum()),
            description="Demo product, invented for local development.",
            identification_source="manual")
        db.add(product)
        await db.flush()
        db.add(ProductAlias(product_id=product.id, alias_type="gtin", alias_value=barcode,
                            data_source_code="demo", confidence=1))
        if cert:
            pc = ProductCertification(product_id=product.id, scheme_code=cert[0],
                                      certificate_identifier=cert[1], current_status=cert[2])
            db.add(pc)
            await db.flush()
            check = CertificationCheck(product_certification_id=pc.id, status=cert[2],
                                       method="manual", notes="Demo data.")
            db.add(check)
            await db.flush()
            pc.last_check_id = check.id
        for i, (rating, title, body) in enumerate(reviews):
            db.add(Review(product_id=product.id, origin="scraped", data_source_code="demo",
                          external_id=f"{slug}-{i}", rating=rating, title=title, body=body))
        if slug == "brightbuild-magnet-set":
            recall = Recall(
                data_source_code="demo", external_id="DEMO-24-001", recall_number="DEMO-24-001",
                title="BrightBuild Magnetic Tiles recalled: magnets can come loose",
                hazard="Loose high-powered magnets are an ingestion hazard to children.",
                remedy="Stop using the tiles and contact the seller for a refund.",
                recall_date=date(2026, 9, 12), url="https://example.invalid/recalls/DEMO-24-001")
            db.add(recall)
            await db.flush()
            db.add(RecallRegion(recall_id=recall.id, country_code="US"))
            rp = RecallProduct(recall_id=recall.id, product_name=name, brand_name=brand_name)
            db.add(rp)
            await db.flush()
            db.add(RecallProductIdentifier(recall_product_id=rp.id, identifier_type="model",
                                           value=model, value_normalized="bbm60"))
        await db.flush()
        emit(db, "product", product.id, "ProductIngested", {"product_id": str(product.id)})


async def staff(db) -> None:
    """A local admin, created only when SEED_ADMIN_PASSWORD is set. No credential is in the repo."""
    settings = get_settings()
    if settings.env != "local" or not settings.seed_admin_password:
        return
    await upsert(db, User, [{
        "email": "admin@telcron.example.com", "display_name": "Local Admin", "role": "admin",
        "password_hash": security.hash_password(settings.seed_admin_password),
        "verification_level": 2, "trust_score": 50, "referral_code": "LOCALADMIN"}], ["email"])


async def main() -> None:
    async with SessionLocal() as db:
        await reference(db)
        await demo(db)
        await staff(db)
        await db.commit()
    await engine.dispose()
    print("seeded")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
