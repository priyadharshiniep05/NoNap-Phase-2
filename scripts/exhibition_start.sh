#!/bin/bash
# One-command start for a NoNap demo: backend (VIDEO_SOURCE=pi) + checks for the Pi and the phone.
# Usage (from the project folder):  bash scripts/exhibition_start.sh
# Stop with Ctrl+C.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs

say() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }

say "Mac address for the iPhone app"
IP=$(ipconfig getifaddr en0)
if [ -z "$IP" ]; then
  echo "   Wi-Fi has no address. Join a Wi-Fi network (or the iPhone's Personal Hotspot) first."
  exit 1
fi
echo "   In the app's server chip enter:   http://$IP:8000"

say "Pi Ethernet (Internet Sharing)"
if ifconfig bridge100 >/dev/null 2>&1; then
  echo "   Internet Sharing is on (Mac = 192.168.2.1 on the Pi cable)."
else
  echo "   Internet Sharing is OFF. Turn it on: System Settings > General > Sharing >"
  echo "   Internet Sharing (share Wi-Fi to USB 10/100 LAN). The Pi needs it for its address."
fi
LINK=$(ifconfig en8 2>/dev/null | awk '/status/{print $2}')
echo "   LAN cable link: ${LINK:-adapter not plugged in}"

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  say "Port 8000 is busy: stopping the previous server"
  lsof -nP -t -iTCP:8000 -sTCP:LISTEN | xargs kill 2>/dev/null
  sleep 2
fi

say "Starting the backend (log: logs/server.out)"
VIDEO_SOURCE=pi PYTHONPATH=".:model" server/.venv/bin/python -m uvicorn server.app.main:app \
  --host 0.0.0.0 --port 8000 >> logs/server.out 2>&1 &
SERVER=$!
trap 'echo; echo "Stopping backend"; kill $SERVER 2>/dev/null; exit 0' INT TERM

for _ in $(seq 1 30); do curl -s -m 2 localhost:8000/health >/dev/null && break; sleep 1; done
curl -s -m 2 localhost:8000/health >/dev/null || { echo "   Backend did not start. See logs/server.out"; kill $SERVER; exit 1; }
echo "   Backend is up: http://$IP:8000"

say "Waiting for Pi camera frames (power the Pi now if it is off; first frames ~90 s after power-on)"
START=$(grep -c "/api/v1/frames" logs/server.out)
while true; do
  NOW=$(grep -c "/api/v1/frames" logs/server.out)
  if [ "$NOW" -gt "$START" ]; then
    echo "   Pi camera is streaming."
    break
  fi
  sleep 3
done

say "Ready"
echo "   1. iPhone: open NoNap, server chip = http://$IP:8000, Test, sign in driver1@nonap.demo / NoNap@123"
echo "   2. Tap Start driving. Camera view card shows the live Pi picture."
echo "   Ctrl+C here stops the backend."
wait $SERVER
