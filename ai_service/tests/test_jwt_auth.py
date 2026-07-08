"""JWT verification (the sole gate on every citizen-scoped endpoint). Tests
generate a throwaway RSA keypair and monkeypatch the public-key loader, so
they're fully self-contained — no dependency on the Spring Boot keypair
existing on disk. Covers the security-critical paths: valid token accepted,
tampered/expired/wrong-type rejected, role gating.
"""
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from ai_service.utils import jwt_auth


@pytest.fixture
def rsa_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    # Force the loader to return OUR public key regardless of on-disk keys.
    monkeypatch.setattr(jwt_auth, "_public_key_cache", public_pem)
    return private_pem, public_pem


def _make_token(private_pem, **claims):
    payload = {"sub": "citizen-123", "role": "CITIZEN", "type": "access",
               "exp": int(time.time()) + 3600, **claims}
    return jwt.encode(payload, private_pem, algorithm="RS256")


def test_valid_token_accepted(rsa_keys):
    private_pem, _ = rsa_keys
    assert jwt_auth._citizen_id_from_token(_make_token(private_pem)) == "citizen-123"


def test_missing_token_rejected(rsa_keys):
    with pytest.raises(HTTPException) as e:
        jwt_auth._citizen_id_from_token(None)
    assert e.value.status_code == 401


def test_tampered_token_rejected(rsa_keys):
    private_pem, _ = rsa_keys
    token = _make_token(private_pem)
    tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    with pytest.raises(HTTPException) as e:
        jwt_auth._citizen_id_from_token(tampered)
    assert e.value.status_code == 401


def test_expired_token_rejected(rsa_keys):
    private_pem, _ = rsa_keys
    token = _make_token(private_pem, exp=int(time.time()) - 10)
    with pytest.raises(HTTPException) as e:
        jwt_auth._citizen_id_from_token(token)
    assert e.value.status_code == 401


def test_refresh_token_rejected_on_access_endpoints(rsa_keys):
    private_pem, _ = rsa_keys
    token = _make_token(private_pem, type="refresh")
    with pytest.raises(HTTPException) as e:
        jwt_auth._citizen_id_from_token(token)
    assert e.value.status_code == 401
    assert "access token" in e.value.detail.lower()


def test_token_signed_by_a_different_key_rejected(rsa_keys):
    _, _ = rsa_keys
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    forged = _make_token(other_pem)  # signed by an attacker key, not ours
    with pytest.raises(HTTPException) as e:
        jwt_auth._citizen_id_from_token(forged)
    assert e.value.status_code == 401


def test_operator_gate_rejects_plain_citizen(rsa_keys, monkeypatch):
    private_pem, _ = rsa_keys
    citizen_token = _make_token(private_pem, role="CITIZEN")

    class _Req:
        cookies = {jwt_auth.ACCESS_TOKEN_COOKIE: citizen_token}

    with pytest.raises(HTTPException) as e:
        jwt_auth.get_current_operator_id(_Req())
    assert e.value.status_code == 403


def test_operator_gate_allows_operator(rsa_keys):
    private_pem, _ = rsa_keys
    op_token = _make_token(private_pem, role="CSC_OPERATOR")

    class _Req:
        cookies = {jwt_auth.ACCESS_TOKEN_COOKIE: op_token}

    assert jwt_auth.get_current_operator_id(_Req()) == "citizen-123"
