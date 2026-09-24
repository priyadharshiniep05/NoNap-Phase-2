#!/usr/bin/env python3
"""
scripts/ws_listen.py — Connect to NoNap WebSocket as a driver and listen for live events.
Usage:
    python scripts/ws_listen.py [--email driver1@nonap.demo] [--password NoNap@123] [--url http://localhost:8000]
"""

import argparse
import asyncio
import json
import sys
import httpx
import websockets


async def main():
    parser = argparse.ArgumentParser(description="NoNap WebSocket Driver Listener")
    parser.add_argument("--email", default="driver1@nonap.demo", help="Driver email")
    parser.add_argument("--password", default="NoNap@123", help="Password")
    parser.add_argument("--url", default="http://localhost:8000", help="NoNap server base URL")
    args = parser.parse_args()

    # 1. Login to get JWT
    print(f"Logging in to {args.url} as {args.email}...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{args.url}/auth/login",
                data={"username": args.email, "password": args.password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                print(f"Login failed ({resp.status_code}): {resp.text}")
                sys.exit(1)

            token_data = resp.json()
            token = token_data.get("access_token")
            print("Login successful! Acquired JWT token.")
        except Exception as e:
            print(f"Error connecting to server: {e}")
            sys.exit(1)

    # 2. Connect to WebSocket
    ws_base = args.url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/ws?token={token}"
    print(f"Connecting to WebSocket: {ws_url}...")

    try:
        async with websockets.connect(ws_url) as ws:
            print("Connected! Listening for live driver status and alerts (Ctrl+C to stop)...")
            print("-" * 70)
            while True:
                msg_raw = await ws.recv()
                try:
                    data = json.loads(msg_raw)
                    msg_type = data.get("type", "unknown")
                    status = data.get("status", "unknown")
                    severity = data.get("severity", "none")
                    confidence = data.get("confidence", 0.0)
                    metrics = data.get("metrics", {})
                    ts = data.get("timestamp", "")
                    message = data.get("message", "")

                    ear = metrics.get("ear", 0.0)
                    mar = metrics.get("mar", 0.0)
                    perclos = metrics.get("perclos", 0.0)

                    # Pretty format based on alert vs telemetry
                    if msg_type in ("alert", "accident") or status in ("drowsy", "accident"):
                        prefix = "🚨 ALERT" if status != "accident" else "💥 ACCIDENT"
                        print(
                            f"[{ts}] {prefix} ({severity.upper()}) | Status: {status.upper()} | "
                            f"Conf: {confidence:.2f} | EAR: {ear:.3f} | MAR: {mar:.3f} | PERCLOS: {perclos:.2f} | "
                            f"{message}"
                        )
                    else:
                        print(
                            f"[{ts}] LIVE STATUS | Status: {status} | "
                            f"Conf: {confidence:.2f} | EAR: {ear:.3f} | MAR: {mar:.3f} | PERCLOS: {perclos:.2f} | "
                            f"{message}"
                        )
                except json.JSONDecodeError:
                    print(f"Received raw: {msg_raw}")
    except KeyboardInterrupt:
        print("\nDisconnected by user.")
    except Exception as e:
        print(f"WebSocket error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
