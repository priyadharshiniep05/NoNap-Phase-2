"""Small lookups shared by detection, alerting, and device services."""

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from server.app.db.models_auth import User, Fleet, FleetDriver


def driver_context(auth_session: Session, driver_id: str) -> Tuple[Optional[User], Optional[str]]:
    """Return (driver user or None, fleet_id or None)."""
    driver = auth_session.query(User).filter(User.id == driver_id).first()
    fd = auth_session.query(FleetDriver).filter(FleetDriver.driver_id == driver_id).first()
    return driver, (fd.fleet_id if fd else None)


def resolve_driver(auth_session: Session, ref: str) -> Optional[User]:
    """Resolve a driver from a UUID or an email address (Pi config accepts either)."""
    ref = (ref or "").strip()
    if not ref:
        return None
    q = auth_session.query(User).filter(User.role == "driver", User.is_active == True)  # noqa: E712
    if "@" in ref:
        return q.filter(User.email == ref.lower()).first()
    return q.filter(User.id == ref).first()


def manager_fleet_id(auth_session: Session, manager_id: str) -> Optional[str]:
    fleet = auth_session.query(Fleet).filter(Fleet.manager_id == manager_id).first()
    return fleet.id if fleet else None


def ws_fleet_id(auth_session: Session, user: User) -> Optional[str]:
    """Fleet scope for a WebSocket connection: the driver's fleet, or the fleet a manager runs."""
    if user.role == "fleet_manager":
        return manager_fleet_id(auth_session, user.id)
    fd = auth_session.query(FleetDriver).filter(FleetDriver.driver_id == user.id).first()
    return fd.fleet_id if fd else None
