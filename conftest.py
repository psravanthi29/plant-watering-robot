"""Global pytest safety net.

Tests must NEVER touch a real Postgres/Supabase database, even if DATABASE_URL
leaks into the environment (e.g. pytest picking up a local .env). Force the db
layer to sqlite for the entire test session before any test imports it.

This exists because a test once connected to live Supabase via DATABASE_URL and
wrote test rows there — see memory/zone-integration.md.
"""

import os

# Remove before importing db so even a fresh import computes USE_PG = False.
os.environ.pop("DATABASE_URL", None)

import db  # noqa: E402

db.USE_PG = False
db.DATABASE_URL = None
