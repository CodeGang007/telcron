"""Sign-up and sign-in say nothing about who has an account (DEF-043), are rate limited (DEF-044),
and keep codes, addresses and provider text out of responses, logs and auth_events (DEF-048)."""

import logging
import uuid
from datetime import timedelta

import pytest
from helpers import API, PASSWORD, signup, verified_user
from pydantic import ValidationError
from sqlalchemy import func, select, text
from starlette.requests import Request

from app.core import ratelimit, security
from app.core.config import Settings, get_settings
from app.models import User, VerificationToken
from app.modules.identity import mailer
from app.modules.identity import service as identity


def _email() -> str:
    return f"{uuid.uuid4().hex[:10]}@example.com"


def _register(client, email, ip_headers=None):
    return client.post(f"{API}/auth/register", headers=ip_headers or {}, json={
        "email": email, "password": PASSWORD, "display_name": "Someone"})


async def _reasons(db, email) -> list[tuple[str, str | None, str | None]]:
    rows = await db.execute(text(
        "select event_type, failure_reason, host(ip_address) from auth_events "
        "where email_attempted = :e order by created_at"), {"e": email})
    return [tuple(r) for r in rows]


@pytest.fixture
def ses(monkeypatch):
    """Mail goes to a list instead of SES: (to, subject)."""
    s = get_settings()
    monkeypatch.setattr(s, "mail_provider", "ses")
    monkeypatch.setattr(s, "mail_from", "codes@example.com")
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(mailer, "_send_ses", lambda to, message: sent.append((to, message[0])))
    return sent


# DEF-043 ---------------------------------------------------------------------------------------

async def test_register_answers_the_same_whether_or_not_the_address_has_an_account(
        client, db, ses, monkeypatch):
    monkeypatch.setattr(get_settings(), "dev_expose_codes", False)  # as deployed
    taken = _email()
    first = await _register(client, taken)
    fresh = await _register(client, _email())
    again = await _register(client, taken)
    assert first.status_code == fresh.status_code == again.status_code == 201
    assert fresh.json() == again.json() == {"email_sent": True, "dev_codes": None}
    # Still one account, one code; the owner was told, not sent a second code.
    assert await db.scalar(select(func.count()).select_from(User).where(User.email == taken)) == 1
    user_id = await db.scalar(select(User.id).where(User.email == taken))
    assert await db.scalar(select(func.count()).select_from(VerificationToken)
                           .where(VerificationToken.user_id == user_id)) == 1
    to_owner = [subject for to, subject in ses if to == taken]
    assert to_owner[0].endswith("is your Telcron code")
    assert to_owner[1] == "Someone tried to create a Telcron account with your email"


async def test_a_locked_account_answers_like_a_wrong_password(client):
    email, _, _ = await verified_user(client)
    for _ in range(5):
        await client.post(f"{API}/auth/login", json={"email": email, "password": "wrong-pass"})
    locked = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    unknown = await client.post(f"{API}/auth/login",
                                json={"email": _email(), "password": PASSWORD})
    assert locked.status_code == unknown.status_code == 401
    assert locked.json() == unknown.json() == {"detail": "invalid_credentials"}


async def test_an_unknown_address_costs_the_same_argon2_work(client, monkeypatch):
    checked = []
    real = security.verify_password
    monkeypatch.setattr(security, "verify_password",
                        lambda h, p: checked.append(p) or real(h, p))
    r = await client.post(f"{API}/auth/login", json={"email": _email(), "password": "guess-1234"})
    assert r.status_code == 401
    assert checked == ["guess-1234"]


# DEF-044 ---------------------------------------------------------------------------------------

async def test_sign_in_is_refused_with_429_after_the_per_address_limit(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_per_email_per_15_minutes", 3)
    email = _email()
    for _ in range(3):
        r = await client.post(f"{API}/auth/login", json={"email": email, "password": "x"})
        assert r.status_code == 401
    for _ in range(2):
        r = await client.post(f"{API}/auth/login", json={"email": email, "password": "x"})
        assert r.status_code == 429 and r.json() == {"detail": "rate_limited"}
        assert 0 < int(r.headers["retry-after"]) <= 900
    # The crossing request is recorded once; the flood after it is not.
    reasons = [reason for _, reason, _ in await _reasons(db, email)]
    assert reasons.count("rate_limited") == 1


@pytest.mark.parametrize("route,setting", [
    ("register", "register_per_ip_per_hour"),
    ("resend", "resend_per_ip_per_hour"),
    ("verify", "verify_per_ip_per_hour"),
    ("login", "login_per_ip_per_15_minutes"),
])
async def test_each_route_has_a_per_client_address_limit(client, monkeypatch, route, setting):
    monkeypatch.setattr(get_settings(), setting, 2)
    bodies = {
        "register": lambda: {"email": _email(), "password": PASSWORD, "display_name": "Someone"},
        "resend": lambda: {"email": _email()},
        "verify": lambda: {"email": _email(), "channel": "email", "code": "000000"},
        "login": lambda: {"email": _email(), "password": "x"},
    }
    statuses = [(await client.post(f"{API}/auth/{route}", json=bodies[route]())).status_code
                for _ in range(3)]
    assert 429 not in statuses[:2] and statuses[2] == 429


async def test_verify_has_a_per_address_limit_on_top_of_five_tries_a_code(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "verify_per_email_per_hour", 2)
    email, codes = await signup(client)
    for _ in range(2):
        r = await client.post(f"{API}/auth/verify",
                              json={"email": email, "channel": "email", "code": "000000"})
        assert r.status_code == 400
    r = await client.post(f"{API}/auth/verify",
                          json={"email": email, "channel": "email", "code": codes["email"]})
    assert r.status_code == 429


async def test_no_more_than_the_daily_cap_of_codes_is_sent_to_one_address(client, ses, monkeypatch):
    monkeypatch.setattr(get_settings(), "mail_per_address_per_day", 2)
    monkeypatch.setattr(identity, "RESEND_GAP", timedelta(0))
    email, _ = await signup(client)  # mail 1
    answers = [await client.post(f"{API}/auth/resend", json={"email": email}) for _ in range(3)]
    assert [a.status_code for a in answers] == [202, 202, 202]  # the cap is never announced
    assert answers[0].json()["dev_codes"] and answers[1].json()["dev_codes"] is None
    assert len([to for to, _ in ses if to == email]) == 2


async def test_the_client_address_is_read_from_a_trusted_proxy_only(client, db, monkeypatch):
    # httpx's test transport connects from 127.0.0.1.
    spoofed = {"X-Forwarded-For": "198.51.100.7, 203.0.113.9"}
    email = _email()
    await client.post(f"{API}/auth/login", headers=spoofed, json={"email": email, "password": "x"})
    monkeypatch.setattr(get_settings(), "trusted_proxies", "127.0.0.1/32")
    await client.post(f"{API}/auth/login", headers=spoofed, json={"email": email, "password": "x"})
    ips = [ip for _, _, ip in await _reasons(db, email)]
    # Untrusted peer: the header is ignored. Trusted peer: the hop it saw, not what the client wrote.
    assert ips == ["127.0.0.1", "203.0.113.9"]


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "client": (peer, 1234), "headers": headers})


def test_client_ip_walks_forwarded_hops_from_the_right(monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8, 172.16.0.0/12")
    assert ratelimit.client_ip(_request("172.18.0.5", "1.2.3.4, 9.9.9.9, 10.0.0.2")) == "9.9.9.9"
    assert ratelimit.client_ip(_request("172.18.0.5", "not-an-ip")) == "172.18.0.5"
    assert ratelimit.client_ip(_request("8.8.8.8", "1.2.3.4")) == "8.8.8.8"
    assert ratelimit.client_ip(_request("testclient")) is None  # never a bad INET value


# DEF-048 ---------------------------------------------------------------------------------------

def test_exposed_codes_are_refused_outside_local_and_test():
    with pytest.raises(ValidationError, match="DEV_EXPOSE_CODES"):
        Settings(env="dev", jwt_secret="s" * 40, dev_expose_codes=True)
    assert Settings(env="dev", jwt_secret="s" * 40, dev_expose_codes=False)
    assert Settings(env="local", dev_expose_codes=True).dev_expose_codes


async def test_mail_logs_mask_the_recipient(client, caplog):
    caplog.set_level(logging.INFO, logger="telcron.mailer")
    email, _ = await signup(client)  # the `log` provider sends nothing and says so
    assert email not in caplog.text
    assert mailer.mask(email) in caplog.text


async def test_auth_events_keep_the_provider_error_code_not_its_text(client, db, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "mail_provider", "ses")
    monkeypatch.setattr(s, "mail_from", "codes@example.com")

    class ClientError(Exception):
        response = {"Error": {"Code": "MessageRejected"}}

    def refuse(to, message):
        raise ClientError(f"Email address is not verified: {to}")
    monkeypatch.setattr(mailer, "_send_ses", refuse)
    email = _email()
    assert (await _register(client, email)).json()["email_sent"] is False
    [(event, reason, _)] = await _reasons(db, email)
    assert (event, reason) == ("otp_failed", "email_not_sent:MessageRejected")
