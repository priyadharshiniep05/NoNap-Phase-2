"""Tests for dual-database sync and reconciliation logic."""

from server.app.db.sync import (
    ensure_global_thresholds,
    ensure_fleet_thresholds,
    ensure_user_thresholds,
    verify_driver_exists,
    get_driver_fleet_id,
    reconcile,
)
from server.app.db.models_ops import Threshold, AlertLog


def test_ensure_thresholds_idempotent(ops_db):
    t1 = ensure_global_thresholds(ops_db)
    t2 = ensure_global_thresholds(ops_db)
    assert t1.id == t2.id
    assert t1.scope == "global"


def test_verify_driver_exists(auth_db, test_driver, test_manager):
    assert verify_driver_exists(auth_db, test_driver.id) is not None
    # Manager is not a driver
    assert verify_driver_exists(auth_db, test_manager.id) is None
    # Non-existent user
    assert verify_driver_exists(auth_db, "non-existent-uuid") is None


def test_get_driver_fleet_id(auth_db, test_driver):
    fleet_id = get_driver_fleet_id(auth_db, test_driver.id)
    assert fleet_id is not None


def test_reconcile_fixes_missing_thresholds(auth_db, ops_db, test_driver):
    # Wipe thresholds
    ops_db.query(Threshold).delete()
    ops_db.commit()

    # Run reconcile
    res = reconcile(auth_db, ops_db)
    assert res["fixed"] >= 1

    # Check user threshold created
    ut = ops_db.query(Threshold).filter(
        Threshold.scope == "user", Threshold.user_id == test_driver.id
    ).first()
    assert ut is not None
