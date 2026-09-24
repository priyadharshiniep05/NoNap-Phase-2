"""Tests for authentication endpoints and password validation."""

import pytest


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["databases"]["auth_db"] == "ok"
    assert data["databases"]["ops_db"] == "ok"


def test_signup_driver_success(client):
    payload = {
        "full_name": "New Driver Alice",
        "email": "alice_test@nonap.demo",
        "password": "SecurePassword@123",
        "role": "driver",
    }
    res = client.post("/auth/signup", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "alice_test@nonap.demo"
    assert data["role"] == "driver"
    assert "id" in data


def test_signup_weak_password_rejected(client):
    payload = {
        "full_name": "Weak User",
        "email": "weak@nonap.demo",
        "password": "password",
        "role": "driver",
    }
    res = client.post("/auth/signup", json=payload)
    assert res.status_code == 400
    assert "Password must" in res.json()["detail"]


def test_signup_duplicate_email(client):
    payload = {
        "full_name": "Dupe User",
        "email": "dupe@nonap.demo",
        "password": "SecurePassword@123",
        "role": "driver",
    }
    res1 = client.post("/auth/signup", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/auth/signup", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_login_success(client, test_driver):
    payload = {
        "email": "test_driver@nonap.demo",
        "password": "NoNap@123",
    }
    res = client.post("/auth/login", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == "driver"
    assert data["user_id"] == test_driver.id


def test_login_invalid_password(client, test_driver):
    payload = {
        "email": "test_driver@nonap.demo",
        "password": "WrongPassword@123",
    }
    res = client.post("/auth/login", json=payload)
    assert res.status_code == 401


def test_get_me(client, driver_headers, test_driver):
    res = client.get("/auth/me", headers=driver_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == test_driver.id
    assert data["role"] == "driver"


def test_token_refresh(client, test_driver):
    # Log in first
    login_res = client.post(
        "/auth/login",
        json={"email": "test_driver@nonap.demo", "password": "NoNap@123"},
    )
    refresh_token = login_res.json()["refresh_token"]

    res = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
