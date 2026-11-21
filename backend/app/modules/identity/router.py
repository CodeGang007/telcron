from fastapi import APIRouter, Request, status
from pydantic import BaseModel, EmailStr

from app.core import ratelimit
from app.core.config import get_settings
from app.core.deps import CurrentUser, Db

from . import service
from .schemas import (
    LoginIn,
    MeOut,
    RefreshIn,
    RegisterIn,
    RegisterOut,
    TokensOut,
    VerifyIn,
    VerifyOut,
)

router = APIRouter(prefix="/auth", tags=["identity"])


def _client(request: Request) -> tuple[str | None, str | None]:
    return ratelimit.client_ip(request), request.headers.get("user-agent")


async def _limit(db: Db, scope: str, email: str, ip: str | None) -> None:
    """429 `rate_limited` over a route's limits (DEF-044); the crossing request is recorded."""
    try:
        await ratelimit.enforce(scope, ip=ip, email=email)
    except ratelimit.RateLimited as exc:
        if exc.first:
            await service.record_throttled(db, scope, email, ip)
        raise


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, db: Db, request: Request) -> RegisterOut:
    ip = _client(request)[0]
    await _limit(db, "register", data.email, ip)
    codes, sent = await service.register(db, data, ip)
    # The same status and body whether or not the address has an account: a new one is emailed its
    # code, an existing one's owner a notice. Locally the code also comes back here.
    return RegisterOut(email_sent=sent,
                       dev_codes=(codes or None) if get_settings().dev_expose_codes else None)


class ResendIn(BaseModel):
    email: EmailStr


@router.post("/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend(data: ResendIn, db: Db, request: Request) -> dict:
    """Send a new email code. The answer is the same whether or not the address has an account."""
    ip = _client(request)[0]
    await _limit(db, "resend", data.email, ip)
    codes = await service.resend(db, data.email, ip)
    return {"sent": True, "dev_codes": codes if codes and get_settings().dev_expose_codes else None}


@router.post("/verify", response_model=VerifyOut)
async def verify(data: VerifyIn, db: Db, request: Request) -> VerifyOut:
    ip = _client(request)[0]
    await _limit(db, "verify", data.email, ip)
    user = await service.verify(db, data.email, data.channel, data.code, ip)
    return VerifyOut(email_verified=user.email_verified_at is not None,
                     phone_verified=user.phone_verified_at is not None,
                     verification_level=user.verification_level)


@router.post("/login", response_model=TokensOut)
async def login(data: LoginIn, db: Db, request: Request) -> TokensOut:
    ip, agent = _client(request)
    await _limit(db, "login", data.email, ip)
    return await service.login(db, data.email, data.password, ip, agent)


@router.post("/refresh", response_model=TokensOut)
async def refresh(data: RefreshIn, db: Db, request: Request) -> TokensOut:
    return await service.refresh(db, data.refresh_token, *_client(request))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshIn, db: Db) -> None:
    await service.logout(db, data.refresh_token)


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser) -> MeOut:
    return MeOut(id=str(user.id), email=user.email, display_name=user.display_name,
                 role=user.role, verification_level=user.verification_level,
                 trust_score=float(user.trust_score),
                 email_verified=user.email_verified_at is not None,
                 phone_verified=user.phone_verified_at is not None)
