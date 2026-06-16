import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from flask import Flask, g, jsonify

import auth
from auth import require_auth

SUPABASE_ENV = ("SUPABASE_PROJECT_URL", "SUPABASE_URL", "SUPABASE_JWT_SECRET")


def _app():
    app = Flask(__name__)

    @app.get("/protected")
    @require_auth
    def protected():
        return jsonify({"user": g.user.get("sub")})

    return app.test_client()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in SUPABASE_ENV:
        monkeypatch.delenv(k, raising=False)


# --- disabled (no config) -----------------------------------------------------

def test_auth_disabled_allows_through():
    r = _app().get("/protected")
    assert r.status_code == 200
    assert r.get_json()["user"] == "dev"


# --- legacy HS256 shared secret -----------------------------------------------

def test_hs256_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "testsecret")
    assert _app().get("/protected").status_code == 401


def test_hs256_rejects_bad_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "testsecret")
    r = _app().get("/protected", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_hs256_accepts_valid_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "testsecret")
    token = jwt.encode({"sub": "user-123", "aud": "authenticated"},
                       "testsecret", algorithm="HS256")
    r = _app().get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.get_json()["user"] == "user-123"


# --- asymmetric (Supabase JWT signing keys via JWKS) --------------------------

class _FakeSigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJWKS:
    def __init__(self, public_key):
        self._key = public_key

    def get_signing_key_from_jwt(self, token):
        return _FakeSigningKey(self._key)


def _es256_token(private_key, iss="https://demo.supabase.co/auth/v1", sub="u1"):
    return jwt.encode({"sub": sub, "aud": "authenticated", "iss": iss},
                      private_key, algorithm="ES256")


def test_asymmetric_accepts_token_signed_by_current_key(monkeypatch):
    priv = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setenv("SUPABASE_PROJECT_URL", "https://demo.supabase.co")
    monkeypatch.setattr(auth, "jwks_client", lambda: _FakeJWKS(priv.public_key()))

    token = _es256_token(priv, sub="user-xyz")
    r = _app().get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.get_json()["user"] == "user-xyz"


def test_asymmetric_rejects_token_signed_by_wrong_key(monkeypatch):
    real = ec.generate_private_key(ec.SECP256R1())
    attacker = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setenv("SUPABASE_PROJECT_URL", "https://demo.supabase.co")
    # JWKS serves the REAL public key, but the token is signed by the attacker
    monkeypatch.setattr(auth, "jwks_client", lambda: _FakeJWKS(real.public_key()))

    token = _es256_token(attacker)
    r = _app().get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
