#!/bin/bash
# Deploy update. Run as user bolshoi-bot from /home/bolshoi-bot/bolshoi-bot
set -e

echo "[update] Pulling latest code from GitHub..."
git pull origin main

echo "[update] Installing/updating dependencies..."
source venv/bin/activate
pip install -r requirements.txt --quiet

echo "[update] Fetching Camoufox browser (skipped if already downloaded)..."
python -m camoufox fetch

echo "[update] Applying database migrations..."
alembic upgrade head

echo "[update] Restarting service..."
sudo systemctl restart bolshoi-bot

echo "[update] Done. Status:"
sudo systemctl status bolshoi-bot --no-pager
