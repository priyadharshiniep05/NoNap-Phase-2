"""Cross-database synchronization logic between auth_db and ops_db.

Provides:
- Application-level referential integrity checks
- Auto-provisioning of default thresholds on user/fleet creation
- Reconcile worker that runs on startup and periodically
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from server.app.db.models_auth import User, Fleet, FleetDriver
from server.app.db.models_ops import Threshold, AlertLog

logger = logging.getLogger("nonap.sync")


def verify_driver_exists(auth_session: Session, driver_id: str) -> Optional[User]:
    """Verify a driver exists in auth_db and has role 'driver'."""
    user = auth_session.query(User).filter(User.id == driver_id).first()
    if user is None or user.role != "driver":
        return None
    return user


def get_driver_fleet_id(auth_session: Session, driver_id: str) -> Optional[str]:
    """Get the fleet_id for a driver, or None if not in any fleet."""
    fd = auth_session.query(FleetDriver).filter(FleetDriver.driver_id == driver_id).first()
    return fd.fleet_id if fd else None


def ensure_user_thresholds(ops_session: Session, user_id: str) -> Threshold:
    """Create default user-scope thresholds row if it doesn't exist."""
    existing = ops_session.query(Threshold).filter(
        Threshold.scope == "user", Threshold.user_id == user_id
    ).first()
    if existing:
        return existing

    t = Threshold(scope="user", user_id=user_id)
    ops_session.add(t)
    ops_session.commit()
    ops_session.refresh(t)
    return t


def ensure_fleet_thresholds(ops_session: Session, fleet_id: str) -> Threshold:
    """Create default fleet-scope thresholds row if it doesn't exist."""
    existing = ops_session.query(Threshold).filter(
        Threshold.scope == "fleet", Threshold.fleet_id == fleet_id
    ).first()
    if existing:
        return existing

    t = Threshold(scope="fleet", fleet_id=fleet_id)
    ops_session.add(t)
    ops_session.commit()
    ops_session.refresh(t)
    return t


def ensure_global_thresholds(ops_session: Session) -> Threshold:
    """Create the global thresholds row if missing."""
    existing = ops_session.query(Threshold).filter(Threshold.scope == "global").first()
    if existing:
        return existing

    t = Threshold(scope="global")
    ops_session.add(t)
    ops_session.commit()
    ops_session.refresh(t)
    return t


def reconcile(auth_session: Session, ops_session: Session) -> dict:
    """Run reconciliation between auth_db and ops_db.

    Returns summary dict with orphan counts and actions taken.
    """
    fixed = 0
    orphans = 0

    # 1. Ensure global thresholds exist
    ensure_global_thresholds(ops_session)

    # 2. Check all drivers have user-scope thresholds
    drivers = auth_session.query(User).filter(User.role == "driver", User.is_active == True).all()
    for driver in drivers:
        existing = ops_session.query(Threshold).filter(
            Threshold.scope == "user", Threshold.user_id == driver.id
        ).first()
        if not existing:
            ensure_user_thresholds(ops_session, driver.id)
            fixed += 1

    # 3. Check all fleets have fleet-scope thresholds
    fleets = auth_session.query(Fleet).all()
    for fleet in fleets:
        existing = ops_session.query(Threshold).filter(
            Threshold.scope == "fleet", Threshold.fleet_id == fleet.id
        ).first()
        if not existing:
            ensure_fleet_thresholds(ops_session, fleet.id)
            fixed += 1

    # 4. Check for orphan alert_logs (driver_id not in auth_db)
    alert_driver_ids = ops_session.query(AlertLog.driver_id).distinct().all()
    for (did,) in alert_driver_ids:
        user = auth_session.query(User).filter(User.id == did).first()
        if user is None:
            orphans += 1
            logger.warning(f"Orphan alert_logs found for missing driver_id={did}")

    # 5. Check for orphan user-scope thresholds
    user_thresholds = ops_session.query(Threshold).filter(Threshold.scope == "user").all()
    for t in user_thresholds:
        user = auth_session.query(User).filter(User.id == t.user_id).first()
        if user is None:
            orphans += 1
            logger.warning(f"Orphan user threshold for missing user_id={t.user_id}")

    return {
        "orphans": orphans,
        "fixed": fixed,
        "drivers_checked": len(drivers),
        "fleets_checked": len(fleets),
    }
