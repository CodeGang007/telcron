from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    display_name: str = Field(min_length=2, max_length=80)
    phone_e164: str | None = Field(None, pattern=r"^\+[1-9]\d{7,14}$")


class RegisterOut(BaseModel):
    user_id: str
    # False when the mail provider refused the code (the member can ask for a new one).
    email_sent: bool = False
    # Present only when DEV_EXPOSE_CODES is on. Never in a deployed environment.
    dev_codes: dict[str, str] | None = None


class VerifyIn(BaseModel):
    email: EmailStr
    channel: Literal["email", "phone"]
    code: str = Field(pattern=r"^\d{6}$")


class VerifyOut(BaseModel):
    email_verified: bool
    phone_verified: bool
    verification_level: int


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class RefreshIn(BaseModel):
    refresh_token: str


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int


class MeOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    verification_level: int
    trust_score: float
    email_verified: bool
    phone_verified: bool
