"""TelcronID: registration, the two codes, sign-in with lockout, rotating refresh tokens."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.events import audit
from app.models import AuthEvent, TrustScoreEvent, User, VerificationToken
from app.models import Session as SessionRow
from app.modules.rewards import service as rewards

from . import mailer
from .schemas import RegisterIn, TokensOut

# channel -> token_purpose, and the auth_event_type written when that channel is confirmed
PURPOSE = {"email": "email_verification", "phone": "phone_otp"}
VERIFIED = {"email": "email_verified", "phone": "phone_verified"}
BLOCKED = ("suspended", "deleted")
LEVEL1_TRUST = Decimal("10.00")


def _now() -> datetime:
    return datetime.now(UTC)


async def _issue_code(db: AsyncSession, user: User, channel: str) -> str:
    purpose = PURPOSE[channel]
    # A new code replaces any earlier unused one for the same purpose.
    await db.execute(update(VerificationToken).where(
        VerificationToken.user_id == user.id, VerificationToken.purpose == purpose,
        VerificationToken.consumed_at.is_(None)).values(consumed_at=_now()))
    code = security.new_code()
    db.add(VerificationToken(
        user_id=user.id, purpose=purpose,
        target=user.email if channel == "email" else user.phone_e164,
        token_hash=security.code_hash(user.id, purpose, code),
        expires_at=_now() + timedelta(minutes=get_settings().code_ttl_minutes)))
    db.add(AuthEvent(user_id=user.id, event_type="otp_sent", email_attempted=user.email))
    return code


async def _deliver(db: AsyncSession, user: User, code: str | None) -> bool:
    """Email the code. A refusal does not undo the sign-up: it is recorded and the member can ask
    for a new code."""
    if code is None:
        return False
    try:
        await mailer.send_code(user.email, code)
        return True
    except mailer.SendFailed as exc:
        db.add(AuthEvent(user_id=user.id, event_type="otp_failed", email_attempted=user.email,
                         failure_reason=f"email_not_sent: {exc}"[:200]))
        return False


RESEND_GAP = timedelta(seconds=60)


async def resend(db: AsyncSession, email: str) -> dict[str, str] | None:
    """A new email code, at most one a minute. Says nothing about whether the address exists."""
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or user.status in BLOCKED or user.email_verified_at is not None:
        return None
    last = await db.scalar(select(VerificationToken.created_at).where(
        VerificationToken.user_id == user.id, VerificationToken.purpose == PURPOSE["email"])
        .order_by(VerificationToken.created_at.desc()).limit(1))
    if last is not None and _now() - last < RESEND_GAP:
        return None
    code = await _issue_code(db, user, "email")
    await _deliver(db, user, code)
    return {"email": code}


async def register(db: AsyncSession, data: RegisterIn,
                   ip: str | None) -> tuple[User, dict[str, str]]:
    if (await db.execute(select(User.id).where(User.email == data.email))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "email_taken")
    # A new account is `pending` (the database default) until its email is confirmed.
    user = User(email=data.email, phone_e164=data.phone_e164, display_name=data.display_name,
                password_hash=security.hash_password(data.password), password_changed_at=_now(),
                referral_code=security.new_referral_code())
    db.add(user)
    await db.flush()
    # Phone codes only once an SMS route exists (ADR-006); the number, if given, is kept.
    channels = ("email", "phone") if get_settings().level1_requires_phone and data.phone_e164 \
        else ("email",)
    codes = {ch: await _issue_code(db, user, ch) for ch in channels}
    await _deliver(db, user, codes.get("email"))
    audit(db, action="user.registered", entity_type="user", entity_id=user.id,
          actor_user_id=user.id)
    return user, codes


async def verify(db: AsyncSession, email: str, channel: str, code: str) -> User:
    user = (await db.execute(select(User).where(User.email == email).with_for_update())
            ).scalar_one_or_none()
    bad = HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_or_expired_code")
    if user is None or user.status in BLOCKED:
        raise bad
    purpose = PURPOSE[channel]
    token = (await db.execute(select(VerificationToken).where(
        VerificationToken.user_id == user.id, VerificationToken.purpose == purpose,
        VerificationToken.consumed_at.is_(None)).order_by(VerificationToken.created_at.desc())
        .limit(1).with_for_update())).scalar_one_or_none()
    s = get_settings()
    if token is None or token.expires_at < _now() or token.attempt_count >= s.code_max_attempts:
        raise bad
    if token.token_hash != security.code_hash(user.id, purpose, code):
        # The attempt must survive the 400, so it is committed on its own.
        token.attempt_count += 1
        db.add(AuthEvent(user_id=user.id, event_type="otp_failed", email_attempted=email,
                         failure_reason=f"{channel}_code_mismatch"))
        await db.commit()
        raise bad

    if channel == "phone" and user.phone_verified_at is None:
        # The schema allows one verified owner per phone number.
        taken = (await db.execute(select(User.id).where(
            User.phone_e164 == user.phone_e164, User.phone_verified_at.is_not(None),
            User.id != user.id))).first()
        if taken:
            raise HTTPException(status.HTTP_409_CONFLICT, "phone_in_use")

    token.consumed_at = _now()
    if channel == "email":
        user.email_verified_at = user.email_verified_at or _now()
        if user.status == "pending":
            user.status = "active"
    else:
        user.phone_verified_at = user.phone_verified_at or _now()
    db.add(AuthEvent(user_id=user.id, event_type=VERIFIED[channel], email_attempted=email))

    phone_ok = user.phone_verified_at is not None or not get_settings().level1_requires_phone
    if user.email_verified_at and phone_ok and user.verification_level < 1:
        user.verification_level = 1
        user.trust_score = LEVEL1_TRUST
        await db.flush()
        db.add(TrustScoreEvent(user_id=user.id, delta=LEVEL1_TRUST, score_after=LEVEL1_TRUST,
                               reason_code="level_1_reached"))
        audit(db, action="user.level_1", entity_type="user", entity_id=user.id,
              actor_user_id=user.id)
        await rewards.earn(db, user.id, "level1_verified", subject_type="user",
                           subject_id=user.id, idempotency_key=f"level1_verified:{user.id}")
    return user


async def _open_session(db: AsyncSession, user: User, ip: str | None, agent: str | None,
                        family_id: uuid.UUID | None = None,
                        family_expires_at: datetime | None = None) -> tuple[SessionRow, TokensOut]:
    refresh, refresh_hash = security.new_refresh_token()
    expires = _now() + timedelta(days=get_settings().refresh_token_days)
    if family_expires_at is not None:
        # A rotated token never outlives the family it belongs to (the schema checks this).
        expires = min(expires, family_expires_at)
    row = SessionRow(user_id=user.id, family_id=family_id or uuid.uuid4(),
                     refresh_token_hash=refresh_hash, expires_at=expires,
                     family_expires_at=family_expires_at or expires, ip_address=ip,
                     user_agent=agent)
    db.add(row)
    await db.flush()
    access, ttl = security.create_access_token(user.id, row.id)
    return row, TokensOut(access_token=access, refresh_token=refresh, expires_in=ttl)


async def login(db: AsyncSession, email: str, password: str, ip: str | None,
                agent: str | None) -> TokensOut:
    s = get_settings()
    user = (await db.execute(select(User).where(User.email == email).with_for_update())
            ).scalar_one_or_none()
    denied = HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    if user is None or user.status in BLOCKED or not user.password_hash:
        db.add(AuthEvent(event_type="login_failed", email_attempted=email,
                         failure_reason="unknown_or_inactive", ip_address=ip))
        await db.commit()
        raise denied
    if user.locked_until and user.locked_until > _now():
        raise HTTPException(status.HTTP_423_LOCKED, "account_locked")
    if not security.verify_password(user.password_hash, password):
        user.failed_login_count += 1
        event = "login_failed"
        if user.failed_login_count >= s.login_max_failures:
            user.locked_until = _now() + timedelta(minutes=s.login_lock_minutes)
            user.failed_login_count = 0
            event = "account_locked"
        db.add(AuthEvent(user_id=user.id, event_type=event, email_attempted=email,
                         failure_reason="bad_password", ip_address=ip))
        await db.commit()
        raise denied
    user.failed_login_count, user.locked_until, user.last_login_at = 0, None, _now()
    _, tokens = await _open_session(db, user, ip, agent)
    await rewards.daily_check_in(db, user.id)
    # `provider` stays empty: auth_provider names outside sign-in providers only.
    db.add(AuthEvent(user_id=user.id, event_type="login_succeeded", email_attempted=email,
                     ip_address=ip, user_agent=agent))
    return tokens


async def refresh(db: AsyncSession, refresh_token: str, ip: str | None,
                  agent: str | None) -> TokensOut:
    denied = HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_refresh_token")
    row = (await db.execute(select(SessionRow).where(
        SessionRow.refresh_token_hash == security.sha256(refresh_token)).with_for_update())
        ).scalar_one_or_none()
    if row is None:
        raise denied
    if row.rotated_at is not None or row.revoked_at is not None:
        # A used token came back: someone holds a copy. The whole family dies.
        await db.execute(update(SessionRow).where(
            SessionRow.family_id == row.family_id, SessionRow.revoked_at.is_(None))
            .values(revoked_at=_now(), revoke_reason="refresh_token_reuse"))
        db.add(AuthEvent(user_id=row.user_id, event_type="token_reuse_detected", ip_address=ip))
        await db.commit()
        raise denied
    if row.expires_at < _now() or row.family_expires_at < _now():
        raise denied
    user = await db.get(User, row.user_id)
    if user is None or user.status in BLOCKED:
        raise denied
    new_row, tokens = await _open_session(db, user, ip, agent, row.family_id,
                                          row.family_expires_at)
    # The old row is superseded, not just rotated: its access tokens stop working too.
    row.rotated_at = row.revoked_at = _now()
    row.revoke_reason = "rotated"
    row.replaced_by_session_id = new_row.id
    db.add(AuthEvent(user_id=user.id, event_type="session_refreshed", ip_address=ip))
    return tokens


async def logout(db: AsyncSession, refresh_token: str) -> None:
    row = (await db.execute(select(SessionRow).where(
        SessionRow.refresh_token_hash == security.sha256(refresh_token)))).scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        await db.execute(update(SessionRow).where(
            SessionRow.family_id == row.family_id, SessionRow.revoked_at.is_(None))
            .values(revoked_at=_now(), revoke_reason="logout"))
        db.add(AuthEvent(user_id=row.user_id, event_type="logout"))
