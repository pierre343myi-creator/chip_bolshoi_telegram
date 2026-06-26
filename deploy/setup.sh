#!/bin/bash
# First-time setup. Run as user bolshoi-bot from /home/bolshoi-bot/chip_bolshoi_telegram
set -e

echo "[setup] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[setup] Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo "[setup] Downloading Camoufox browser..."
python -m camoufox fetch

echo "[setup] Applying database migrations..."
alembic upgrade head

echo ""
echo "[setup] Done. Now run these sudo commands manually:"
echo ""
echo "  sudo mkdir -p /var/log/bolshoi-bot"
echo "  sudo chown bolshoi-bot:bolshoi-bot /var/log/bolshoi-bot"
echo "  sudo cp deploy/bolshoi-bot.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable bolshoi-bot"
echo "  sudo systemctl start bolshoi-bot"
echo "  sudo systemctl status bolshoi-bot"
