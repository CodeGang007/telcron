"""Local conveniences on top of the database's own seeds. Idempotent.

Reference data (sources, categories, hazard dimensions, earn rules, levels) and the fictional
demo products are the database's: `make db-seed`, `make db-next` and `make db-sample`. This
script adds only what the application needs to be usable on a developer's machine or the dev
environment, and does nothing at all unless ENV is local or dev.
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.core import security
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.models import User

ADMIN_EMAIL = "admin@telcron.example.com"  # `.local` addresses do not pass the sign-in form


async def local_admin(db) -> str:
    """An admin who can sign in, created only when SEED_ADMIN_PASSWORD is set. The demo data's
    own accounts have no password. No credential lives in the repository."""
    password = get_settings().seed_admin_password
    if not password:
        return "admin: skipped (SEED_ADMIN_PASSWORD is not set)"
    values = {
        "email": ADMIN_EMAIL, "display_name": "Local Admin", "role": "admin", "status": "active",
        "password_hash": security.hash_password(password), "verification_level": 2,
        "trust_score": 50, "referral_code": "LOCALADMIN", "phone_e164": "+15550100099",
        "email_verified_at": text("now()"), "phone_verified_at": text("now()")}
    await db.execute(insert(User).values(**values).on_conflict_do_update(
        index_elements=["email"], set_={"password_hash": values["password_hash"]}))
    return f"admin: {ADMIN_EMAIL}"


async def local_coin_delay(db) -> str:
    """Earned coins wait out a fraud-review window (10 minutes by default). For demos that is
    shortened by rewriting the rule rows of the LOCAL database."""
    seconds = get_settings().coin_confirm_delay_seconds
    if seconds is None:
        return "coin delay: unchanged"
    await db.execute(text("update coin_earn_rules set confirmation_delay = "
                          "make_interval(secs => :s)"), {"s": seconds})
    return f"coin delay: {seconds}s"


async def main() -> None:
    if get_settings().env not in ("local", "dev"):
        print("ENV is neither local nor dev: nothing to do")  # noqa: T201
        return
    async with SessionLocal() as db:
        done = [await local_admin(db), await local_coin_delay(db)]
        await db.commit()
    await engine.dispose()
    print("\n".join(done))  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
