"""Password hashing, access tokens, and the hashed one-time secrets (refresh tokens, codes)."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import get_settings

_hasher = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:  # malformed hash: treat as a failed login, never a 500
        return False


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


def verify_dummy(password: str) -> None:
    """The same argon2 work as a real check, for an address with no account: without it, how long
    a failed sign-in takes would say whether the address is registered (DEF-043)."""
    verify_password(_dummy_hash(), password)


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(UTC)
    ttl = s.access_token_minutes * 60
    token = jwt.encode(
        {"sub": str(user_id), "sid": str(session_id), "iat": now,
         "exp": now + timedelta(seconds=ttl)},
        s.jwt_secret, algorithm=ALGORITHM,
    )
    return token, ttl


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])


def sha256(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


def new_refresh_token() -> tuple[str, bytes]:
    token = secrets.token_urlsafe(48)
    return token, sha256(token)


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def code_hash(user_id: uuid.UUID, purpose: str, code: str) -> bytes:
    """Six digits alone would collide on the unique token_hash; bind to user and purpose."""
    return sha256(f"{user_id}:{purpose}:{code}")


def new_referral_code() -> str:
    return secrets.token_hex(4).upper()
