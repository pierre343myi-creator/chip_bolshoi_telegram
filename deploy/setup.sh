#!/bin/bash
# First-time setup. Run as user bolshoi-bot from /home/bolshoi-bot/bolshoi-bot
set -e

echo "[setup] Creating virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

echo "[setup] Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo "[setup] Downloading Yandex Cloud SSL certificate..."
mkdir -p ~/.postgresql
wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" \
     -O ~/.postgresql/root.crt --quiet
chmod 0600 ~/.postgresql/root.crt
echo "       Certificate saved to ~/.postgresql/root.crt"

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
