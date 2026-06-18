#!/usr/bin/env bash
# One-command redeploy after pushing changes to GitHub.
#   bash deploy/deploy.sh
set -euo pipefail

cd "$HOME/plant-watering-robot"
echo "== Pulling latest =="
git pull --ff-only
echo "== Updating deps =="
.venv/bin/pip install -r requirements.txt
echo "== Restarting service =="
sudo systemctl restart thotamaali
sleep 2
systemctl status thotamaali --no-pager | head -5
echo "Done."
