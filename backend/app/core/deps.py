"""Request dependencies: who is calling, and what their verification level and role allow."""

import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session as SessionRow
from app.models import User

from .db import get_session
from .security import decode_access_token

# scope="function": the transaction commits BEFORE the response is sent. With the default
# (request scope) a client could receive its tokens and call back before the row existed.
Db = Annotated[AsyncSession, Depends(get_session, scope="function")]
_bearer = HTTPBearer(auto_error=False)


async def optional_user(
    db: Db, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User | None:
    if creds is None:
        return None
    try:
        claims = decode_access_token(creds.credentials)
        user_id, session_id = uuid.UUID(claims["sub"]), uuid.UUID(claims["sid"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token") from exc
    row = (await db.execute(
        select(User, SessionRow.revoked_at)
        .join(SessionRow, SessionRow.user_id == User.id)
        .where(User.id == user_id, SessionRow.id == session_id)
    )).first()
    if row is None or row[1] is not None or row[0].status in ("suspended", "deleted"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session_revoked")
    return row[0]


async def current_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    return user


def require_level(level: int) -> Callable:
    async def dep(user: Annotated[User, Depends(current_user)]) -> User:
        if user.verification_level < level:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"verification_level_{level}_required")
        return user
    return dep


def require_role(*roles: str) -> Callable:
    async def dep(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "role_not_allowed")
        return user
    return dep


OptionalUser = Annotated[User | None, Depends(optional_user)]
CurrentUser = Annotated[User, Depends(current_user)]
Level1User = Annotated[User, Depends(require_level(1))]
