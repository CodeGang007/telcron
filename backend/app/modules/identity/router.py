from fastapi import APIRouter, Request, status
from pydantic import BaseModel, EmailStr

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
    return (request.client.host if request.client else None, request.headers.get("user-agent"))


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, db: Db, request: Request) -> RegisterOut:
    user, codes = await service.register(db, data, _client(request)[0])
    # The email code is sent by mailer.py (SES when deployed). Locally it also comes back here.
    return RegisterOut(user_id=str(user.id),
                       dev_codes=codes if get_settings().dev_expose_codes else None)


class ResendIn(BaseModel):
    email: EmailStr


@router.post("/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend(data: ResendIn, db: Db) -> dict:
    """Send a new email code. The answer is the same whether or not the address has an account."""
    codes = await service.resend(db, data.email)
    return {"sent": True, "dev_codes": codes if codes and get_settings().dev_expose_codes else None}


@router.post("/verify", response_model=VerifyOut)
async def verify(data: VerifyIn, db: Db) -> VerifyOut:
    user = await service.verify(db, data.email, data.channel, data.code)
    return VerifyOut(email_verified=user.email_verified_at is not None,
                     phone_verified=user.phone_verified_at is not None,
                     verification_level=user.verification_level)


@router.post("/login", response_model=TokensOut)
async def login(data: LoginIn, db: Db, request: Request) -> TokensOut:
    return await service.login(db, data.email, data.password, *_client(request))


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
