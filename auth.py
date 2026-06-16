"""Supabase-JWT auth for the JSON API.

The Expo app signs in with Supabase Auth and sends the resulting JWT as
``Authorization: Bearer <token>`` on every API call. We verify that token here.

Two verification modes, auto-selected by env:
  * **Asymmetric (preferred)** — set ``SUPABASE_PROJECT_URL`` (e.g.
    https://<ref>.supabase.co). Supabase signs tokens with its "JWT signing
    keys"; we verify against the project's public JWKS endpoint. No secret is
    stored server-side.
  * **Legacy HS256** — set ``SUPABASE_JWT_SECRET`` (older projects with a shared
    JWT secret).

If neither is set, auth is DISABLED (dev/local + the current pre-login deploy
keep working). Configure one to switch the API to authenticated.

Separate from the device token on POST /api/reading: a headless sensor can't do
an interactive Supabase login, so it keeps using the shared SENSOR_API_TOKEN.
"""

import os
from functools import wraps

import jwt
from flask import g, jsonify, request

JWT_AUDIENCE = "authenticated"
# Supabase asymmetric signing keys are ECC (ES256) by default; allow RSA/EdDSA too.
ASYMMETRIC_ALGORITHMS = ["ES256", "RS256", "EdDSA"]

_jwks_client = None  # cached PyJWKClient (fetches + caches public keys)


def _project_url():
    url = os.environ.get("SUPABASE_PROJECT_URL") or os.environ.get("SUPABASE_URL")
    return url.rstrip("/") if url else None


def _secret():
    return os.environ.get("SUPABASE_JWT_SECRET")


def auth_enabled() -> bool:
    """Read at call time so tests/late env-setting take effect."""
    return bool(_project_url() or _secret())


def jwks_client():
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            f"{_project_url()}/auth/v1/.well-known/jwks.json"
        )
    return _jwks_client


def verify_token(token: str) -> dict:
    """Decode + verify a Supabase JWT. Raises jwt.PyJWTError on failure."""
    if _project_url():  # asymmetric — verify against the public JWKS
        signing_key = jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(
            token, signing_key, algorithms=ASYMMETRIC_ALGORITHMS,
            audience=JWT_AUDIENCE, issuer=f"{_project_url()}/auth/v1",
        )
    # legacy shared-secret projects
    return jwt.decode(
        token, _secret(), algorithms=["HS256"], audience=JWT_AUDIENCE
    )


def require_auth(fn):
    """Route decorator: require a valid Supabase JWT (no-op when auth disabled)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not auth_enabled():
            g.user = {"sub": "dev", "email": "dev@local", "auth": "disabled"}
            return fn(*args, **kwargs)

        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "missing bearer token"}), 401
        try:
            g.user = verify_token(header[len("Bearer "):])
        except jwt.PyJWTError as exc:
            return jsonify({"error": f"invalid token: {exc}"}), 401
        return fn(*args, **kwargs)

    return wrapper
