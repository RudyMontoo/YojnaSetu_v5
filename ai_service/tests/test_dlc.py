"""Agent 12 (DLC) — the public-key JWK importer, which is the trust anchor of
the whole offline-proof scheme (a bad key here means unverifiable or
forgeable proofs). Pure/no-Mongo: the full verify loop is covered by the live
e2e (see docs/status/COMPLETED.md), this pins the JWK-parsing boundary."""
import json

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt.algorithms import RSAAlgorithm

from ai_service.routers.dlc_router import _canonical_public_key


def _valid_rsa_jwk():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    return {"kty": jwk["kty"], "n": jwk["n"], "e": jwk["e"], "alg": "RS256", "use": "sig"}


def test_valid_rsa_jwk_imports():
    pub = _canonical_public_key(_valid_rsa_jwk())
    assert isinstance(pub, rsa.RSAPublicKey)
    assert pub.key_size == 2048


def test_non_rsa_key_rejected():
    with pytest.raises(HTTPException) as e:
        _canonical_public_key({"kty": "EC", "crv": "P-256", "x": "a", "y": "b"})
    assert e.value.status_code == 400


def test_malformed_jwk_rejected():
    with pytest.raises(HTTPException) as e:
        _canonical_public_key({"kty": "RSA", "n": "!!not-base64!!", "e": "AQAB"})
    assert e.value.status_code == 400


def test_empty_jwk_rejected():
    with pytest.raises(HTTPException) as e:
        _canonical_public_key({})
    assert e.value.status_code == 400
