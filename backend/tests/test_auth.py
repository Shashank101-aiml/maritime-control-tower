"""Tests for the authentication boundary.

These deliberately clear the `authenticated_by_default` override from
conftest so they exercise the real dependency, not the stand-in.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app

client = TestClient(app)

# Routes that must never be reachable without a token. The approvals
# endpoint is the one that mattered most: before this slice, anyone who
# could reach the API could approve an agent's pending action.
PROTECTED = [
    ("post", "/api/governance/approvals/1/approve"),
    ("post", "/api/governance/approvals/1/reject"),
    ("get", "/api/governance/agents"),
    ("get", "/api/governance/audit"),
    ("get", "/api/dashboard"),
    ("get", "/api/vessels"),
    ("get", "/api/events"),
    ("get", "/api/run-workflow"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_routes_reject_anonymous(unauthenticated, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401, f"{method.upper()} {path} was reachable anonymously"


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_routes_reject_garbage_token(unauthenticated, method, path):
    response = getattr(client, method)(
        path, headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert response.status_code == 401


def test_health_stays_public(unauthenticated):
    """Load balancers and the frontend's status indicator poll this
    without credentials."""
    assert client.get("/health").status_code == 200


def test_login_rejects_bad_password(unauthenticated):
    response = client.post(
        "/api/auth/login", data={"username": "admin", "password": "definitely-wrong"}
    )
    assert response.status_code == 401


def test_login_does_not_leak_whether_account_exists(unauthenticated):
    """Both failures must return the same message, or the endpoint
    becomes a username oracle."""
    missing = client.post(
        "/api/auth/login", data={"username": "no-such-user", "password": "x"}
    )
    wrong_pw = client.post(
        "/api/auth/login", data={"username": "admin", "password": "x"}
    )
    assert missing.status_code == wrong_pw.status_code == 401
    assert missing.json()["detail"] == wrong_pw.json()["detail"]


# --- token / password primitives ---------------------------------------

def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong", hashed)


def test_password_over_72_bytes_does_not_raise():
    """bcrypt hard-errors above 72 bytes; long passwords must still work."""
    long_password = "a" * 200
    hashed = hash_password(long_password)
    assert verify_password(long_password, hashed)


def test_verify_rejects_malformed_hash():
    """A corrupt hash in the database should fail the login, not 500."""
    assert verify_password("anything", "not-a-bcrypt-hash") is False


def test_token_roundtrip():
    token = create_access_token(42)
    assert decode_access_token(token) == "42"


def test_expired_token_is_rejected():
    token = create_access_token(42, expires_minutes=-1)
    assert decode_access_token(token) is None


def test_token_signed_with_another_key_is_rejected():
    from jose import jwt
    forged = jwt.encode({"sub": "1"}, "attacker-key", algorithm="HS256")
    assert decode_access_token(forged) is None
