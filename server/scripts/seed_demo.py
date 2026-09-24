"""Seed database with realistic demo accounts, fleets, thresholds, and historical alerts."""

import os
import sys
from datetime import datetime, timezone, timedelta
import random

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from server.app.core.security import hash_password
from server.app.db.auth_db import get_auth_session_factory, create_auth_tables
from server.app.db.ops_db import get_ops_session_factory, create_ops_tables
from server.app.db.models_auth import User, Fleet, FleetDriver
from server.app.db.models_ops import Threshold, AlertLog, SessionStat
from server.app.db.sync import reconcile


def seed_demo_data():
    print("Initializing SQLite tables...")
    create_auth_tables()
    create_ops_tables()

    auth_factory = get_auth_session_factory()
    ops_factory = get_ops_session_factory()

    auth_db = auth_factory()
    ops_db = ops_factory()

    try:
        # Clear existing demo data to be idempotent
        print("Cleaning previous demo data...")
        auth_db.query(FleetDriver).delete()
        auth_db.query(Fleet).delete()
        auth_db.query(User).delete()
        auth_db.commit()

        ops_db.query(AlertLog).delete()
        ops_db.query(Threshold).delete()
        ops_db.query(SessionStat).delete()
        ops_db.commit()

        pw_hash = hash_password("NoNap@123")

        # 1. Create Fleet Manager
        manager = User(
            full_name="Fleet Manager Sarah",
            email="manager@nonap.demo",
            password_hash=pw_hash,
            role="fleet_manager",
            is_active=True,
        )
        auth_db.add(manager)
        auth_db.commit()
        auth_db.refresh(manager)
        print(f"Created manager: {manager.email} (id={manager.id})")

        # 2. Create Fleet
        fleet = Fleet(
            manager_id=manager.id,
            name="Apex Logistics Express",
        )
        auth_db.add(fleet)
        auth_db.commit()
        auth_db.refresh(fleet)
        print(f"Created fleet: {fleet.name} (id={fleet.id})")

        # 3. Create Drivers
        driver_configs = [
            ("Alex Rivera", "driver1@nonap.demo"),
            ("Brenda Vance", "driver2@nonap.demo"),
            ("Carlos Diaz", "driver3@nonap.demo"),
        ]

        created_drivers = []
        for name, email in driver_configs:
            driver = User(
                full_name=name,
                email=email,
                password_hash=pw_hash,
                role="driver",
                is_active=True,
            )
            auth_db.add(driver)
            auth_db.commit()
            auth_db.refresh(driver)

            # Assign to fleet
            fd = FleetDriver(fleet_id=fleet.id, driver_id=driver.id)
            auth_db.add(fd)
            auth_db.commit()

            created_drivers.append(driver)
            print(f"Created driver: {driver.full_name} ({driver.email})")

        # 4. Create Thresholds in ops_db
        # Global
        global_thresh = Threshold(
            scope="global",
            ear_threshold=0.21,
            mar_threshold=0.60,
            perclos_threshold=0.40,
            eyes_closed_seconds=1.5,
            alert_cooldown_seconds=30.0,
        )
        ops_db.add(global_thresh)

        # Fleet scope
        fleet_thresh = Threshold(
            scope="fleet",
            fleet_id=fleet.id,
            ear_threshold=0.22,
            mar_threshold=0.58,
            perclos_threshold=0.38,
            eyes_closed_seconds=1.4,
            alert_cooldown_seconds=25.0,
        )
        ops_db.add(fleet_thresh)

        # User scopes
        for d in created_drivers:
            user_thresh = Threshold(
                scope="user",
                user_id=d.id,
                ear_threshold=0.21,
                mar_threshold=0.60,
                perclos_threshold=0.40,
                eyes_closed_seconds=1.5,
                alert_cooldown_seconds=30.0,
            )
            ops_db.add(user_thresh)

        ops_db.commit()
        print("Provisioned global, fleet, and driver thresholds.")

        # 5. Generate ~40 realistic alerts across the past 7 days
        now = datetime.now(timezone.utc)
        print("Generating historical alert logs...")

        alert_count = 0
        for i in range(42):
            driver = random.choice(created_drivers)
            # Days ago: 0 to 6
            days_ago = random.randint(0, 6)
            # Pick a realistic driving hour (late night 22-04 or post-lunch 13-16)
            hour = random.choice([1, 2, 3, 4, 13, 14, 15, 22, 23])
            minute = random.randint(0, 59)
            second = random.randint(0, 59)

            detected_time = now - timedelta(days=days_ago)
            detected_time = detected_time.replace(hour=hour, minute=minute, second=second)

            # Alert types
            roll = random.random()
            if roll < 0.55:
                atype = "drowsy"
                severity = random.choice(["medium", "high", "critical"])
                ear = round(random.uniform(0.10, 0.18), 3)
                mar = round(random.uniform(0.12, 0.25), 3)
                perclos = round(random.uniform(0.42, 0.75), 3)
            elif roll < 0.90:
                atype = "yawning"
                severity = random.choice(["low", "medium"])
                ear = round(random.uniform(0.20, 0.28), 3)
                mar = round(random.uniform(0.65, 0.95), 3)
                perclos = round(random.uniform(0.15, 0.35), 3)
            else:
                atype = "accident"
                severity = "critical"
                ear = 0.05
                mar = 0.20
                perclos = 0.90

            ack = days_ago > 0 or random.random() > 0.4
            ack_by = manager.full_name if ack else None

            log = AlertLog(
                driver_id=driver.id,
                fleet_id=fleet.id,
                type=atype,
                severity=severity,
                confidence=round(random.uniform(0.85, 0.99), 2),
                ear=ear,
                mar=mar,
                perclos=perclos,
                source=random.choice(["webcam", "pi"]),
                detected_at=detected_time,
                acknowledged=ack,
                acknowledged_by=ack_by,
            )
            ops_db.add(log)
            alert_count += 1

        ops_db.commit()
        print(f"Successfully generated {alert_count} demo alert logs.")

        # Reconcile
        reconcile_summary = reconcile(auth_db, ops_db)
        print(f"Sync reconcile verify: {reconcile_summary}")
        print("\nDemo seed complete!")
        print("Manager login: manager@nonap.demo / NoNap@123")
        print("Driver logins:  driver1@nonap.demo / NoNap@123")
        print("               driver2@nonap.demo / NoNap@123")
        print("               driver3@nonap.demo / NoNap@123")

    finally:
        auth_db.close()
        ops_db.close()


if __name__ == "__main__":
    seed_demo_data()
