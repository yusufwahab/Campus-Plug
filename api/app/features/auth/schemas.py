import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def normalise_phone(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+234") and len(digits) == 14:
        return digits
    if digits.startswith("234") and len(digits) == 13:
        return "+" + digits
    if digits.startswith("0") and len(digits) == 11:
        return "+234" + digits[1:]
    raise ValueError("Enter a valid Nigerian phone number")


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return normalise_phone(v) if v else None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class MfaVerifyIn(BaseModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=6)


class MfaEnrollIn(BaseModel):
    mfa_token: str


class PhoneSendIn(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalise_phone(v)


class PhoneVerifyIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TokenOut(BaseModel):
    token: str | None = None
    mfa_required: bool = False
    mfa_enrolled: bool = False
    mfa_token: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    phone: str | None
    phone_verified: bool
    role: str
    status: str
    campus_id: int | None
    location_id: int | None
    interests: list[str]
    onboarded: bool
    mfa_enabled: bool
    notify_optional: bool
    permissions: list[str] = []


class ProfileIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    notify_optional: bool | None = None


class OnboardingIn(BaseModel):
    campus_id: int
    location_id: int | None = None
    interests: list[str] = Field(default_factory=list, max_length=8)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
