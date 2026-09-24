"""CLI WebSocket listener for testing real-time stream without opening a browser or app."""

import asyncio
import json
import sys
import websockets
import httpx


async def listen(email: str = "driver1@nonap.demo", password: str = "NoNap@123", url: str = "http://localhost:8000"):
    print(f"Logging in as {email}...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{url}/auth/login", json={"email": email, "password": password})
            if resp.status_code != 200:
                print(f"Login failed: {resp.status_code} - {resp.text}")
                return
            data = resp.json()
            token = data["access_token"]
            role = data["role"]
            name = data["full_name"]
            print(f"Authenticated as {name} ({role})")
        except Exception as e:
            print(f"Could not connect to server at {url}: {e}")
            return

    ws_url = url.replace("http://", "ws://").replace("https://", "wss://") + f"/ws?token={token}"
    print(f"Connecting to WebSocket: {ws_url} ...")

    try:
        async with websockets.connect(ws_url) as ws:
            print("Connected! Listening for live telemetry and drowsiness alerts (Ctrl+C to quit)...\n")
            while True:
                msg_raw = await ws.recv()
                msg = json.loads(msg_raw)
                mtype = msg.get("type")
                status = msg.get("status")
                severity = msg.get("severity")
                message = msg.get("message")
                driver_name = msg.get("driver_name")
                metrics = msg.get("metrics", {})

                if mtype == "alert":
                    print(f"\033[91m[ALERT - {severity.upper()}]\033[0m {message} | EAR={metrics.get('ear')} MAR={metrics.get('mar')} PERCLOS={metrics.get('perclos')}")
                elif mtype == "telemetry":
                    print(f"\033[92m[TELEMETRY]\033[0m {driver_name}: {status} | EAR={metrics.get('ear')} MAR={metrics.get('mar')} PERCLOS={metrics.get('perclos')}")
                else:
                    print(f"[EVENT:{mtype}] {message}")
    except KeyboardInterrupt:
        print("\nListener stopped.")
    except Exception as e:
        print(f"WebSocket error: {e}")


if __name__ == "__main__":
    email_arg = sys.argv[1] if len(sys.argv) > 1 else "driver1@nonap.demo"
    asyncio.run(listen(email=email_arg))
