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
echo "  Fleet Manager:  manager@nonap.demo / NoNap@123"
echo "  Driver 1:       driver1@nonap.demo / NoNap@123"
echo "  Driver 2:       driver2@nonap.demo / NoNap@123"
echo "  Driver 3:       driver3@nonap.demo / NoNap@123"
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
exec uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --reload
