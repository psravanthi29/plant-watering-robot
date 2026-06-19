# Deploying to AWS EC2 (ap-south-1, co-located with Supabase)

The app runs as **gunicorn behind nginx** on a `t4g.micro` Ubuntu instance in
`ap-south-1` (Mumbai) — the same AWS region as the Supabase Postgres project, so the
DB hop is intra-datacenter (~1–5 ms) instead of the cross-region ~500 ms we hit on
Render. See `memory/deployment-hosting.md` for the why.

## First-time setup
```bash
# on the EC2 box (ubuntu user)
cd ~
git clone https://github.com/psravanthi29/plant-watering-robot.git
cd plant-watering-robot

# create .env with the secrets (DO NOT commit it; it's gitignored)
nano .env
#   DATABASE_URL=...            # the same Supabase (Mumbai) URL used on Render
#   SUPABASE_PROJECT_URL=...    # https://<ref>.supabase.co
#   GOOGLE_API_KEY=...          # optional (vision)
#   SENSOR_API_TOKEN=...        # optional (POST /api/reading)

bash deploy/setup_ec2.sh
```

## Redeploy after pushing changes
```bash
bash deploy/deploy.sh
```

## Updating the web app (Expo → Flask)
Flask serves the **exported Expo web bundle** at `mobile/dist/` (so thotamaali.com
*is* the app). The EC2 box has no Node, so the bundle is **built locally and committed**:
```bash
cd mobile && npm run build:web   # == expo export -p web → mobile/dist/
git add mobile/dist && git commit -m "Rebuild web bundle" && git push
# then on the box:
ssh thotamaali 'cd plant-watering-robot && bash deploy/deploy.sh'
```
Do this whenever you change anything under `mobile/`. (Native app builds are separate,
via Expo Go / EAS, and just call `https://thotamaali.com/api`.)

## Files
- `thotamaali.service` — systemd unit; runs gunicorn on 127.0.0.1:8000
  (`--workers 1 --threads 8 --timeout 120`). Reads `.env` via the app's load_dotenv().
- `nginx-thotamaali.conf` — nginx server block, proxies :80 → :8000.
- `setup_ec2.sh` — installs packages, venv, the service, and nginx.
- `deploy.sh` — git pull + pip install + restart.

## After it's serving on :80
1. Allocate an **Elastic IP** and associate it (so the IP survives stop/start).
2. Point **thotamaali.com** (Cloudflare) at the Elastic IP (A record).
3. Add **TLS** (Cloudflare in front, or certbot on the box).
4. Once stable, retire the Render service.
