"""Recall ingestion: parsing with exact answers, then a job end to end with the feed replaced."""

import copy
import hashlib
import json
import pathlib
import re
from datetime import date

import httpx
from helpers import API, product_id, staff_user, verified_user
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models import OutboxEvent, Recall, RecallProduct, SourceRecord
from app.modules.ingestion import cpsc, raw_store
from app.modules.ingestion.service import normalized, run_job
from app.workers.handlers import screening

RECORDS = json.loads((pathlib.Path(__file__).parent / "fixtures" / "cpsc_recalls.json").read_text())


def feed(records):
    async def fetch(start: date, end: date) -> list[dict]:
        return copy.deepcopy(records)
    return fetch


def test_brand_comes_from_the_title():
    assert cpsc.brand_from_title("Bodum USA Recalls 5.9 Million French Presses") == "Bodum"
    assert cpsc.brand_from_title("DREO Recalls DR-HSH015 Space Heaters Due to Fire") == "DREO"
    assert cpsc.brand_from_title("HAIARA Power Banks Recalled Due to Risk of Injury") is None


def test_model_numbers_are_read_from_running_text():
    assert cpsc.models_in("DREO Space Heaters, model DR-HSH015") == ["DR-HSH015"]
    assert cpsc.models_in("electric kettles, models KW-10, KW-12 and KW-15.") == [
        "KW-10", "KW-12", "KW-15"]
    assert cpsc.models_in("model numbers 12345 or 67890 printed on the base") == ["12345", "67890"]
    # A word is not a model number, however it is introduced.
    assert cpsc.models_in("the model shown in the photo") == []


def test_a_feed_record_becomes_a_recall():
    heater, pajamas, kettles = (cpsc.parse(r) for r in RECORDS)
    assert (heater.external_id, heater.recall_number) == ("990001", "27-TEST-1")
    assert heater.recall_date == date(2026, 10, 29)
    assert heater.units_affected == "About 12,000"
    product = heater.products[0]
    assert (product.brand, product.manufacturer) == ("HeatWave", "HeatWave USA Inc.")
    assert product.identifiers == [("model_number", "HW-1500")]
    assert pajamas.products[0].identifiers == [("gtin", "850055599991")]
    assert [v for _, v in kettles.products[0].identifiers] == ["KW-10", "KW-12", "KW-15"]
    assert kettles.products[0].manufacturer == "Kettleworks Ltd."


def test_identifiers_are_normalised_like_the_registry():
    assert normalized("model_number", "hw-1500") == "HW1500"
    assert normalized("gtin", "850055599991") == "00850055599991"


async def start_job(client, admin, **body) -> dict:
    r = await client.post(f"{API}/ingest", headers=admin, json=body)
    assert r.status_code == 202, r.text
    return r.json()


async def test_only_an_admin_starts_a_job(client, db):
    _, _, member = await verified_user(client)
    _, moderator = await staff_user(client, db, role="moderator")
    for headers in (member, moderator):
        assert (await client.post(f"{API}/ingest", headers=headers, json={})).status_code == 403
    _, admin = await staff_user(client, db, role="admin")
    r = await client.post(f"{API}/ingest", headers=admin,
                          json={"date_start": "2026-10-31", "date_end": "2026-10-01"})
    assert r.status_code == 422 and r.json()["detail"] == "bad_date_range"


async def test_a_job_imports_recalls_and_rescreens_what_they_affect(client, db):
    slug = "heatwave-1500-heater"
    pid = await product_id(db, slug)
    before = (await client.get(f"{API}/products/{slug}/passport")).json()
    assert before["status_badge"] == "needs_information"  # nothing checked yet
    _, admin = await staff_user(client, db, role="admin")

    job = await start_job(client, admin, date_start="2026-10-01", date_end="2026-10-31")
    assert (job["status"], job["trigger"]) == ("queued", "admin")
    queued = (await db.execute(select(OutboxEvent).where(
        OutboxEvent.event_type == "IngestionRequested",
        OutboxEvent.payload["job_id"].astext == job["id"]))).scalar_one()
    stats = await run_job(queued.payload["job_id"], fetch=feed(RECORDS))  # what the Worker does
    assert stats == {"fetched": 3, "new": 3, "changed": 0, "unchanged": 0, "errors": 0,
                     "products_rescreened": 1}
    done = (await client.get(f"{API}/jobs/{job['id']}", headers=admin)).json()
    assert done["status"] == "succeeded" and done["finished_at"]

    # The notices are public and searchable.
    listed = (await client.get(f"{API}/recalls", params={"q": "kettle shock"})).json()
    assert [r["recall_number"] for r in listed] == ["27-TEST-3"]
    assert listed[0]["products"] == ["Kettleworks electric kettles"]

    # The registry product the recall names is re-screened, and now reads recalled.
    event = (await db.execute(select(OutboxEvent).where(
        OutboxEvent.event_type == "RecallImported",
        OutboxEvent.payload["product_id"].astext == str(pid)))).scalar_one()
    await screening.handle("RecallImported", event.payload)
    passport = (await client.get(f"{API}/products/{slug}/passport")).json()
    assert passport["status_badge"] == "recalled"
    assert passport["recall_matches"][0]["title"].startswith("HeatWave USA Recalls HW-1500")

    # The same content again stops at its hash: nothing new, nothing re-screened.
    again = await start_job(client, admin)
    assert await run_job(again["id"], fetch=feed(RECORDS)) == {
        "fetched": 3, "new": 0, "changed": 0, "unchanged": 3, "errors": 0,
        "products_rescreened": 0}

    # An edited notice is recognised as changed and replaces what was stored, without duplicates.
    edited = copy.deepcopy(RECORDS)
    edited[2]["Remedies"][0]["Name"] = "Contact Kettleworks for a full refund."
    changed = await start_job(client, admin)
    stats = await run_job(changed["id"], fetch=feed(edited))
    assert (stats["changed"], stats["unchanged"], stats["new"]) == (1, 2, 0)
    kettle = (await db.execute(select(Recall).where(Recall.external_id == "990003"))).scalar_one()
    await db.refresh(kettle)
    assert kettle.remedy == "Contact Kettleworks for a full refund."
    assert await db.scalar(select(func.count()).select_from(RecallProduct).where(
        RecallProduct.recall_id == kettle.id)) == 1


async def test_one_bad_record_does_not_lose_the_rest(client, db):
    _, admin = await staff_user(client, db, role="admin")
    good = copy.deepcopy(RECORDS[1])
    good["RecallID"], good["RecallNumber"] = 990010, "27-TEST-10"
    broken = {"Title": "A record with no id", "Products": []}
    job = await start_job(client, admin)
    stats = await run_job(job["id"], fetch=feed([broken, good]))
    assert (stats["new"], stats["errors"]) == (1, 1)
    view = (await client.get(f"{API}/jobs/{job['id']}", headers=admin)).json()
    assert view["status"] == "partial" and "KeyError" in view["error"]


async def test_an_unreachable_source_fails_the_job_visibly(client, db):
    _, admin = await staff_user(client, db, role="admin")

    async def down(start, end):
        raise httpx.ConnectError("connection refused")

    job = await start_job(client, admin)
    await run_job(job["id"], fetch=down)
    view = (await client.get(f"{API}/jobs/{job['id']}", headers=admin)).json()
    assert view["status"] == "failed" and "ConnectError" in view["error"]
    assert (await client.get(f"{API}/jobs", headers=admin)).json()[0]["id"] == job["id"]


def test_a_raw_copy_is_named_by_source_day_and_content():
    digest = hashlib.sha256(b"{}").digest()
    assert raw_store.key_for("cpsc", digest, date(2026, 11, 2)) == (
        f"raw/cpsc/2026/11/02/{digest.hex()}.json")


def fresh_records(first_id: int) -> list[dict]:
    """The feed's records under ids no other test imports, so each test sees them as new."""
    records = copy.deepcopy(RECORDS)
    for n, record in enumerate(records):
        record["RecallID"], record["RecallNumber"] = first_id + n, f"27-RAW-{first_id + n}"
    return records


async def rows_of(db, job_id) -> list[SourceRecord]:
    return list((await db.execute(select(SourceRecord).where(
        SourceRecord.ingestion_job_id == job_id))).scalars())


async def test_with_the_raw_store_on_each_new_record_is_kept_outside_the_database(
        client, db, monkeypatch):
    stored: dict[str, bytes] = {}

    async def put(key: str, body: bytes) -> None:
        stored[key] = body
    monkeypatch.setattr(get_settings(), "raw_store", "s3")
    monkeypatch.setattr(raw_store, "put", put)
    _, admin = await staff_user(client, db, role="admin")
    records = fresh_records(990100)

    job = await start_job(client, admin)
    stats = await run_job(job["id"], fetch=feed(records))
    assert (stats["new"], stats["raw_copied"], stats["errors"]) == (3, 3, 0)
    rows = await rows_of(db, job["id"])
    assert len(rows) == 3
    for row in rows:
        assert re.fullmatch(r"raw/cpsc/\d{4}/\d{2}/\d{2}/[0-9a-f]{64}\.json",
                            row.payload_storage_key)
        # The stored bytes are the record: they hash to the row's content hash.
        assert hashlib.sha256(stored[row.payload_storage_key]).digest() == row.payload_sha256
        assert row.payload is None  # the schema keeps exactly one copy (source_records_chk1)

    # A repeat of the same content stores nothing, in the database or outside it.
    again = await start_job(client, admin)
    assert (await run_job(again["id"], fetch=feed(records)))["unchanged"] == 3
    assert len(stored) == 3 and await rows_of(db, again["id"]) == []


async def test_with_the_raw_store_off_nothing_leaves_the_database(client, db, monkeypatch):
    async def must_not_call(key: str, body: bytes) -> None:
        raise AssertionError("the raw store is off")
    monkeypatch.setattr(raw_store, "put", must_not_call)
    _, admin = await staff_user(client, db, role="admin")

    job = await start_job(client, admin)
    stats = await run_job(job["id"], fetch=feed(fresh_records(990200)))
    assert stats["new"] == 3 and "raw_copied" not in stats
    rows = await rows_of(db, job["id"])
    assert len(rows) == 3
    assert all(r.payload is not None and r.payload_storage_key is None for r in rows)


async def test_a_failed_upload_keeps_the_record_in_the_database(client, db, monkeypatch):
    async def down(key: str, body: bytes) -> None:
        raise ConnectionError("store unreachable")
    monkeypatch.setattr(get_settings(), "raw_store", "s3")
    monkeypatch.setattr(raw_store, "put", down)
    _, admin = await staff_user(client, db, role="admin")

    job = await start_job(client, admin)
    stats = await run_job(job["id"], fetch=feed(fresh_records(990300)))
    assert (stats["new"], stats["errors"], stats["raw_copy_failed"]) == (3, 0, 3)
    view = (await client.get(f"{API}/jobs/{job['id']}", headers=admin)).json()
    assert view["status"] == "succeeded"
    rows = await rows_of(db, job["id"])
    assert len(rows) == 3
    assert all(r.payload is not None and r.payload_storage_key is None for r in rows)
