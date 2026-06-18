#!/usr/bin/env bash
# One-time server setup for the plant-watering Flask app on Ubuntu (EC2, ap-south-1).
# Run from the repo root AFTER creating .env:   bash deploy/setup_ec2.sh
set -euo pipefail

APP_DIR="$HOME/plant-watering-robot"
cd "$APP_DIR"

if [ ! -f .env ]; then
  echo "!! No .env found in $APP_DIR."
  echo "   Create it first (DATABASE_URL, SUPABASE_PROJECT_URL, etc.), then re-run."
  echo "   Without it the app falls back to a local empty SQLite DB, not Supabase."
  exit 1
fi

echo "== Installing system packages =="
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip nginx git

echo "== Python venv + deps =="
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "== gunicorn systemd service =="
sudo cp deploy/thotamaali.service /etc/systemd/system/thotamaali.service
sudo systemctl daemon-reload
sudo systemctl enable --now thotamaali
sudo systemctl restart thotamaali

echo "== nginx reverse proxy =="
sudo cp deploy/nginx-thotamaali.conf /etc/nginx/sites-available/thotamaali
sudo ln -sf /etc/nginx/sites-available/thotamaali /etc/nginx/sites-enabled/thotamaali
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo
echo "== Done. Quick checks: =="
echo "  systemctl status thotamaali --no-pager"
echo "  curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/readings"
echo "  curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/api/readings"
