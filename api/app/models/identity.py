from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow

ROLES = ("buyer", "seller", "admin", "super_admin")
ADMIN_ROLES = ("admin", "super_admin")
PERMISSIONS = ("verifier", "hall_rep")


class Campus(Base):
    __tablename__ = "campuses"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class Location(Base):
    """A hall or general area on a campus. No maps and no room numbers."""

    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10), default="hall")  # hall | area
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    auth_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # Supabase user id
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(100))  # local adapter only
    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(12), default="buyer", index=True)
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | suspended | banned
    campus_id: Mapped[int | None] = mapped_column(ForeignKey("campuses.id"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    interests: Mapped[Any] = mapped_column(JSON, default=list)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_optional: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES


class UserPermission(Base):
    """Limited add-ons an Admin can give to normal accounts."""

    __tablename__ = "user_permissions"
    __table_args__ = (UniqueConstraint("user_id", "permission"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    permission: Mapped[str] = mapped_column(String(20))
    hall_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class PhoneCode(Base):
    __tablename__ = "phone_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    phone: Mapped[str] = mapped_column(String(20))
    code_hash: Mapped[str] = mapped_column(String(100))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
