"""What the API tests share: making members and staff the way a person would, through the API."""

import uuid

from sqlalchemy import select, update

from app.models import Product, User

API = "/api/v1"
PASSWORD = "correct-horse-battery"  # noqa: S105


def new_phone() -> str:
    return "+1555" + f"{uuid.uuid4().int % 10**7:07d}"


async def signup(client, name="Tester", phone=None):
    email = f"{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(f"{API}/auth/register", json={
        "email": email, "password": PASSWORD, "display_name": name,
        "phone_e164": phone or new_phone()})
    assert r.status_code == 201, r.text
    return email, r.json()["dev_codes"]


async def login(client, email):
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    tokens = r.json()
    return tokens, {"Authorization": f"Bearer {tokens['access_token']}"}


async def verified_user(client, name="Tester"):
    email, codes = await signup(client, name)
    for channel in codes:  # email only, unless the phone requirement is on (ADR-006)
        r = await client.post(f"{API}/auth/verify", json={
            "email": email, "channel": channel, "code": codes[channel]})
        assert r.status_code == 200, r.text
    assert r.json()["verification_level"] == 1
    tokens, headers = await login(client, email)
    return email, tokens, headers


async def staff_user(client, db, role="moderator", name="Reviewer"):
    """A verified member promoted to the safety team. The role is read on every request."""
    email, _, headers = await verified_user(client, name)
    await db.execute(update(User).where(User.email == email).values(role=role))
    await db.commit()
    return email, headers


async def me(client, headers) -> dict:
    return (await client.get(f"{API}/auth/me", headers=headers)).json()


async def product_id(db, slug) -> uuid.UUID:
    return (await db.execute(select(Product.id).where(Product.public_slug == slug))).scalar_one()
