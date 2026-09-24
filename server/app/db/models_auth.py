"""Auth database SQLAlchemy models (DB1: identity)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import declarative_base, relationship

AuthBase = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(AuthBase):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(SAEnum("driver", "fleet_manager", name="user_role"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)


class Fleet(AuthBase):
    __tablename__ = "fleets"

    id = Column(String, primary_key=True, default=_uuid)
    manager_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    manager = relationship("User", foreign_keys=[manager_id])


class FleetDriver(AuthBase):
    __tablename__ = "fleet_drivers"

    fleet_id = Column(String, ForeignKey("fleets.id"), primary_key=True)
    driver_id = Column(String, ForeignKey("users.id"), primary_key=True)
    added_at = Column(DateTime, default=_utcnow)
