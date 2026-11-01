#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "=========================================================="
echo "                   NoNap Dev Environment                  "
echo "=========================================================="

# Find local IP
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")

echo "Macbook Local IP: http://$IP:8000"
echo "WebSocket URL:    ws://$IP:8000/ws"
echo "API Docs:         http://localhost:8000/docs"
echo ""
echo "Demo Accounts:"
echo "  Fleet Manager:  manager@nonap.demo (Ananya Iyer) / NoNap@123"
echo "  Driver 1:       driver1@nonap.demo (Priyadarshini Prasanna) / NoNap@123"
echo "  Driver 2:       driver2@nonap.demo (Nishant Sharma [Simulated]) / NoNap@123"
echo "  Driver 3:       driver3@nonap.demo (Namrata Rao [Simulated]) / NoNap@123"
echo "  Driver 4:       driver4@nonap.demo (Rohan Gupta [Simulated]) / NoNap@123"
echo "  Driver 5:       driver5@nonap.demo (Nikhil Menon [Simulated]) / NoNap@123"
echo "=========================================================="

# Activate virtualenv and run server
source server/.venv/bin/activate
export PYTHONPATH="$DIR"

# Seed if database does not exist
if [ ! -f "server/data/auth.db" ]; then
    echo "First time setup: Seeding SQLite database..."
    python server/scripts/seed_demo.py
fi

echo "Starting NoNap server on 0.0.0.0:8000..."
export VIDEO_SOURCE="${VIDEO_SOURCE:-pi}"
echo "Frame source:     VIDEO_SOURCE=$VIDEO_SOURCE   (pi = Raspberry Pi / simulate_pi.py, webcam = MacBook webcam)"
echo "Pi config.ini:    server_url = http://$IP:8000"
# No --reload: a reload would drop in-flight alert state mid-demo.
exec uvicorn server.app.main:app --host 0.0.0.0 --port 8000
