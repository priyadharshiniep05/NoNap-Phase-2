"""Seed database with realistic Indian demo accounts, fleets, thresholds, and historical alerts."""

import os
import sys
from datetime import datetime, timezone, timedelta
import random
import zoneinfo

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from server.app.core.security import hash_password
from server.app.core.timezone import IST
from server.app.db.auth_db import get_auth_session_factory, create_auth_tables
from server.app.db.ops_db import get_ops_session_factory, create_ops_tables
from server.app.db.models_auth import User, Fleet, FleetDriver
from server.app.db.models_ops import Threshold, AlertLog, SessionStat, Device
from server.app.db.migrate import upgrade_ops_db
from server.app.db.sync import reconcile


def seed_demo_data():
    print("Initializing SQLite tables...")
    create_auth_tables()
    create_ops_tables()
    upgrade_ops_db()

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
        ops_db.query(Device).delete()
        ops_db.commit()

        pw_hash = hash_password("NoNap@123")

        # 1. Create Fleet Manager (Indian context)
        manager = User(
            full_name="Ananya Iyer",
            email="manager@nonap.demo",
            password_hash=pw_hash,
            role="fleet_manager",
            is_active=True,
        )
        auth_db.add(manager)
        auth_db.commit()
        auth_db.refresh(manager)
        print(f"Created manager: {manager.full_name} ({manager.email})")

        # 2. Create Fleet (Bengaluru hub)
        fleet = Fleet(
            manager_id=manager.id,
            name="Apex Logistics India (Bengaluru)",
        )
        auth_db.add(fleet)
        auth_db.commit()
        auth_db.refresh(fleet)
        print(f"Created fleet: {fleet.name} (id={fleet.id})")

        # 3. Create Drivers:
        # Priyadarshini Prasanna (Live MacBook / iPhone Driver)
        # Other drivers marked as [Simulated] for fleet overview
        driver_configs = [
            ("Priyadarshini Prasanna", "driver1@nonap.demo"),
            ("Nishant Sharma [Simulated]", "driver2@nonap.demo"),
            ("Namrata Rao [Simulated]", "driver3@nonap.demo"),
            ("Rohan Gupta [Simulated]", "driver4@nonap.demo"),
            ("Nikhil Menon [Simulated]", "driver5@nonap.demo"),
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
        global_thresh = Threshold(
            scope="global",
            ear_threshold=0.21,
            mar_threshold=0.60,
            perclos_threshold=0.40,
            eyes_closed_seconds=1.5,
            alert_cooldown_seconds=10.0,
        )
        ops_db.add(global_thresh)

        fleet_thresh = Threshold(
            scope="fleet",
            fleet_id=fleet.id,
            ear_threshold=0.21,
            mar_threshold=0.60,
            perclos_threshold=0.40,
            eyes_closed_seconds=1.5,
            alert_cooldown_seconds=10.0,
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
                alert_cooldown_seconds=10.0,
            )
            ops_db.add(user_thresh)

        ops_db.commit()
        print("Provisioned thresholds with 10s cooldown.")

        # 5. Generate ~45 realistic alerts in IST across the past 7 days
        now_ist = datetime.now(IST)
        print("Generating historical alert logs in Asia/Kolkata (IST)...")

        alert_count = 0
        reasons_map = {
            "drowsy": ["eyes_closed", "perclos"],
            "yawning": ["yawn"],
            "accident": ["impact_sensor", "sudden_deceleration"],
        }

        for i in range(45):
            driver = random.choice(created_drivers)
            days_ago = random.randint(0, 6)
            # Pick driving hours in IST (e.g., late night 23:00 - 05:00 or post-lunch 13:00 - 16:00)
            hour = random.choice([0, 1, 2, 3, 4, 13, 14, 15, 22, 23])
            minute = random.randint(0, 59)
            second = random.randint(0, 59)

            detected_time = now_ist - timedelta(days=days_ago)
            detected_time = detected_time.replace(hour=hour, minute=minute, second=second)
            if detected_time > now_ist:  # never seed alerts in the future
                detected_time -= timedelta(days=1)

            roll = random.random()
            if roll < 0.60:
                atype = "drowsy"
                severity = random.choice(["medium", "high", "critical"])
                ear = round(random.uniform(0.10, 0.17), 3)
                mar = round(random.uniform(0.12, 0.24), 3)
                perclos = round(random.uniform(0.42, 0.72), 3)
            elif roll < 0.90:
                atype = "yawning"
                severity = random.choice(["low", "medium"])
                ear = round(random.uniform(0.20, 0.28), 3)
                mar = round(random.uniform(0.62, 0.92), 3)
                perclos = round(random.uniform(0.12, 0.32), 3)
            else:
                atype = "accident"
                severity = "critical"
                ear = 0.05
                mar = 0.20
                perclos = 0.90

            ack = days_ago > 0 or random.random() > 0.35
            ack_by = manager.full_name if ack else None
            # Level-model fields. Response times are deliberately left empty:
            # only real "I'm awake" taps record them.
            level = {"low": 1, "medium": 1, "high": 2, "critical": 3}[severity]
            status = "acknowledged" if ack else ("resolved" if level == 1 else "unacknowledged")

            # Mark source as simulated for simulated drivers
            # Seeded history is demo data, never a measurement: always "simulated"
            source = "simulated"

            log = AlertLog(
                driver_id=driver.id,
                fleet_id=fleet.id,
                type=atype,
                severity=severity,
                confidence=round(random.uniform(0.88, 0.99), 2),
                ear=ear,
                mar=mar,
                perclos=perclos,
                source=source,
                detected_at=detected_time,
                acknowledged=ack,
                acknowledged_by=ack_by,
                level=None if atype == "accident" else level,
                status=None if atype == "accident" else status,
                reason={"drowsy": "eyes_closed", "yawning": "yawn"}.get(atype),
            )
            ops_db.add(log)
            alert_count += 1

        ops_db.commit()
        print(f"Successfully generated {alert_count} demo alert logs.")

        # 6. Register camera devices + vehicles. They show offline until a real
        #    heartbeat arrives (the Pi, or tools/simulate_pi.py).
        vehicles = ["KA 01 AB 4521", "KA 05 MN 7310", "KA 03 HX 2208", "KA 51 C 9084", "KA 02 JP 6617"]
        for i, d in enumerate(created_drivers):
            ops_db.add(Device(
                id="nonap-pi-01" if i == 0 else f"nonap-pi-sim-{i:02d}",
                driver_id=d.id,
                vehicle=vehicles[i % len(vehicles)],
                camera_backend="picamera" if i == 0 else None,
                created_at=datetime.now(IST).replace(tzinfo=None),
            ))
        ops_db.commit()
        print("Registered devices: nonap-pi-01 -> Priyadarshini Prasanna (KA 01 AB 4521)")

        # Reconcile
        reconcile_summary = reconcile(auth_db, ops_db)
        print(f"Sync reconcile verify: {reconcile_summary}")
        print("\nDemo seed complete!")
        print(f"Manager login: manager@nonap.demo ({manager.full_name}) / NoNap@123")
        print("Driver logins:  driver1@nonap.demo (Priyadarshini Prasanna) / NoNap@123")
        print("               driver2@nonap.demo (Nishant Sharma [Simulated]) / NoNap@123")
        print("               driver3@nonap.demo (Namrata Rao [Simulated]) / NoNap@123")
        print("               driver4@nonap.demo (Rohan Gupta [Simulated]) / NoNap@123")
        print("               driver5@nonap.demo (Nikhil Menon [Simulated]) / NoNap@123")

    finally:
        auth_db.close()
        ops_db.close()


if __name__ == "__main__":
    seed_demo_data()
