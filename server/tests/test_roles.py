"""Comprehensive tests verifying strict 3-tier role separation.

Rules:
- Drivers CANNOT access any /fleet/* endpoints (MUST return 403 Forbidden).
- Fleet managers CANNOT access any /driver/* personal endpoints (MUST return 403 Forbidden).
- Unauthenticated requests to either MUST return 401 Unauthorized.
"""

import pytest


# ==========================================
# 1. DRIVER ACCESS PERMISSIONS
# ==========================================

def test_driver_can_access_driver_profile(client, driver_headers, test_driver):
    res = client.get("/driver/profile", headers=driver_headers)
    assert res.status_code == 200
    assert res.json()["id"] == test_driver.id


def test_driver_can_access_driver_stats(client, driver_headers, test_driver):
    res = client.get("/driver/stats", headers=driver_headers)
    assert res.status_code == 200
    assert res.json()["driver_id"] == test_driver.id


def test_driver_can_access_driver_alerts(client, driver_headers):
    res = client.get("/driver/alerts", headers=driver_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_driver_can_access_driver_thresholds(client, driver_headers):
    res = client.get("/driver/thresholds", headers=driver_headers)
    assert res.status_code == 200
    assert res.json()["scope"] == "user"


# ==========================================
# 2. DRIVER ATTEMPTS TO ACCESS FLEET ROUTES (MUST BE 403)
# ==========================================

def test_driver_cannot_access_fleet_overview(client, driver_headers):
    res = client.get("/fleet/overview", headers=driver_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_driver_cannot_access_fleet_drivers(client, driver_headers):
    res = client.get("/fleet/drivers", headers=driver_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_driver_cannot_access_fleet_thresholds(client, driver_headers):
    res = client.get("/fleet/thresholds", headers=driver_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_driver_cannot_access_fleet_alerts(client, driver_headers):
    res = client.get("/fleet/alerts", headers=driver_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


# ==========================================
# 3. FLEET MANAGER ACCESS PERMISSIONS
# ==========================================

def test_manager_can_access_fleet_overview(client, manager_headers):
    res = client.get("/fleet/overview", headers=manager_headers)
    assert res.status_code == 200
    assert "fleet_id" in res.json()


def test_manager_can_access_fleet_drivers(client, manager_headers):
    res = client.get("/fleet/drivers", headers=manager_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_manager_can_access_fleet_thresholds(client, manager_headers):
    res = client.get("/fleet/thresholds", headers=manager_headers)
    assert res.status_code == 200
    assert res.json()["scope"] == "fleet"


def test_manager_can_access_fleet_alerts(client, manager_headers):
    res = client.get("/fleet/alerts", headers=manager_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ==========================================
# 4. FLEET MANAGER ATTEMPTS TO ACCESS DRIVER ROUTES (MUST BE 403)
# ==========================================

def test_manager_cannot_access_driver_profile(client, manager_headers):
    res = client.get("/driver/profile", headers=manager_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_manager_cannot_access_driver_stats(client, manager_headers):
    res = client.get("/driver/stats", headers=manager_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_manager_cannot_access_driver_alerts(client, manager_headers):
    res = client.get("/driver/alerts", headers=manager_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_manager_cannot_access_driver_thresholds(client, manager_headers):
    res = client.get("/driver/thresholds", headers=manager_headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


# ==========================================
# 5. UNAUTHENTICATED REQUESTS (MUST BE 401)
# ==========================================

def test_unauthenticated_driver_profile_rejected(client):
    res = client.get("/driver/profile")
    assert res.status_code == 401


def test_unauthenticated_fleet_overview_rejected(client):
    res = client.get("/fleet/overview")
    assert res.status_code == 401
