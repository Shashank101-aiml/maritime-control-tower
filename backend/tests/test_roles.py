"""Tests for role-based access (operator < supervisor < admin) and admin
user management.

These run against an isolated in-memory database so they never touch real
users or approvals, and they drop conftest's blanket "always admin"
override so the real role checks run.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.auth import get_current_active_superuser, get_current_active_user
from app.api.dependencies.database import get_db
from app.core.constants import UserRole
from app.core.security import hash_password
from app.database.base import Base
from app.main import app
from app.models.governance import ApprovalRequest, AuditLog
from app.models.user import User

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents exist

PASSWORD = "correct-horse-1"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.clear()
    session.close()


def make_user(db, username, role):
    user = User(
        email=f"{username}@example.com", username=username, full_name=username.title(),
        hashed_password=hash_password(PASSWORD), role=role, is_active=True,
        is_superuser=role == UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def act_as(user):
    """Sign in as `user` without going through login; the role checks and
    everything below them still run for real."""
    app.dependency_overrides.pop(get_current_active_superuser, None)
    app.dependency_overrides[get_current_active_user] = lambda: user


def login(username, password=PASSWORD):
    return client.post("/api/auth/login", data={"username": username, "password": password})


def audit_rows(db, event_type):
    db.expire_all()
    return db.query(AuditLog).filter(AuditLog.event_type == event_type).all()


# --- governance gating ---------------------------------------------------

RESTRICTED = [
    # (method, path, lowest role allowed)
    ("post", "/api/governance/approvals/999/approve", UserRole.SUPERVISOR),
    ("post", "/api/governance/approvals/999/reject", UserRole.SUPERVISOR),
    ("get", "/api/governance/executions", UserRole.SUPERVISOR),
    ("get", "/api/governance/audit", UserRole.SUPERVISOR),
    ("post", "/api/governance/agents/none/status?status=QUARANTINED", UserRole.ADMIN),
    ("get", "/api/users", UserRole.ADMIN),
]
RANK = {UserRole.OPERATOR: 1, UserRole.SUPERVISOR: 2, UserRole.ADMIN: 3}


@pytest.mark.parametrize("role", list(UserRole))
@pytest.mark.parametrize("method,path,minimum", RESTRICTED)
def test_each_route_allows_only_its_minimum_role_and_above(db, role, method, path, minimum):
    act_as(make_user(db, f"u_{role.value}", role))
    status = getattr(client, method)(path).status_code
    if RANK[role] >= RANK[minimum]:
        assert status != 403, f"{role.value} should reach {method.upper()} {path}"
    else:
        assert status == 403, f"{role.value} must not reach {method.upper()} {path}"


@pytest.mark.parametrize("role", list(UserRole))
def test_every_role_can_still_read_pending_approvals(db, role):
    act_as(make_user(db, f"u_{role.value}", role))
    assert client.get("/api/governance/approvals").status_code == 200


def test_superuser_flag_counts_as_admin_even_with_a_default_role(db):
    user = make_user(db, "flagged", UserRole.OPERATOR)
    user.is_superuser = True
    db.commit()
    act_as(user)
    assert client.get("/api/users").status_code == 200


def test_approval_records_the_real_reviewer(db):
    approval = ApprovalRequest(agent_id="risk-agent", execution_id="e1", status="PENDING")
    db.add(approval)
    db.commit()
    act_as(make_user(db, "sam", UserRole.SUPERVISOR))

    assert client.post(f"/api/governance/approvals/{approval.id}/approve").status_code == 200

    db.expire_all()
    assert db.get(ApprovalRequest, approval.id).reviewer_id == "sam"
    assert audit_rows(db, "APPROVAL_GRANTED")[0].actor == "sam"


def test_operator_cannot_approve_and_the_request_stays_pending(db):
    approval = ApprovalRequest(agent_id="risk-agent", execution_id="e1", status="PENDING")
    db.add(approval)
    db.commit()
    act_as(make_user(db, "olive", UserRole.OPERATOR))

    assert client.post(f"/api/governance/approvals/{approval.id}/approve").status_code == 403

    db.expire_all()
    assert db.get(ApprovalRequest, approval.id).status == "PENDING"


# --- user management -----------------------------------------------------

NEW_USER = {"username": "newop", "email": "newop@example.com", "password": PASSWORD, "role": "operator"}


def test_admin_creates_a_user_who_can_then_sign_in(db):
    act_as(make_user(db, "root", UserRole.ADMIN))

    created = client.post("/api/users", json=NEW_USER)

    assert created.status_code == 201
    assert created.json()["role"] == "operator" and "password" not in created.json()
    assert "hashed_password" not in created.json()
    assert audit_rows(db, "USER_CREATED")[0].actor == "root"

    app.dependency_overrides.pop(get_current_active_user)
    signed_in = login("newop")
    assert signed_in.status_code == 200
    assert signed_in.json()["user"]["role"] == "operator"


def test_creating_an_admin_sets_the_superuser_flag(db):
    act_as(make_user(db, "root", UserRole.ADMIN))
    created = client.post("/api/users", json={**NEW_USER, "role": "admin"})
    assert created.status_code == 201
    db.expire_all()
    assert db.query(User).filter(User.username == "newop").one().is_superuser is True


@pytest.mark.parametrize("bad", [
    {"password": "short"},
    {"username": "no spaces"},
    {"email": "not-an-email"},
    {"role": "captain"},
])
def test_invalid_new_user_is_rejected(db, bad):
    act_as(make_user(db, "root", UserRole.ADMIN))
    assert client.post("/api/users", json={**NEW_USER, **bad}).status_code == 422


def test_duplicate_username_or_email_is_a_conflict(db):
    act_as(make_user(db, "root", UserRole.ADMIN))
    assert client.post("/api/users", json=NEW_USER).status_code == 201
    assert client.post("/api/users", json=NEW_USER).status_code == 409
    other_name_same_email = {**NEW_USER, "username": "another"}
    assert client.post("/api/users", json=other_name_same_email).status_code == 409


def test_admin_changes_a_role_and_the_superuser_flag_follows(db):
    admin = make_user(db, "root", UserRole.ADMIN)
    target = make_user(db, "tina", UserRole.OPERATOR)
    act_as(admin)

    promoted = client.patch(f"/api/users/{target.id}", json={"role": "admin"})
    assert promoted.status_code == 200 and promoted.json()["role"] == "admin"
    db.expire_all()
    assert db.get(User, target.id).is_superuser is True

    demoted = client.patch(f"/api/users/{target.id}", json={"role": "supervisor"})
    assert demoted.status_code == 200
    db.expire_all()
    assert db.get(User, target.id).is_superuser is False
    assert len(audit_rows(db, "USER_UPDATED")) == 2


def test_admin_cannot_change_own_role_or_deactivate_themselves(db):
    admin = make_user(db, "root", UserRole.ADMIN)
    act_as(admin)
    assert client.patch(f"/api/users/{admin.id}", json={"role": "operator"}).status_code == 400
    assert client.patch(f"/api/users/{admin.id}", json={"is_active": False}).status_code == 400
    db.expire_all()
    assert db.get(User, admin.id).role == UserRole.ADMIN and db.get(User, admin.id).is_active


def test_deactivated_user_loses_access_immediately_and_cannot_sign_in(db):
    admin = make_user(db, "root", UserRole.ADMIN)
    target = make_user(db, "dana", UserRole.OPERATOR)

    token = login("dana").json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    act_as(admin)
    assert client.patch(f"/api/users/{target.id}", json={"is_active": False}).status_code == 200
    app.dependency_overrides.pop(get_current_active_user)

    # The token was valid a moment ago; it must stop working at once.
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert login("dana").status_code == 403


def test_password_reset_replaces_the_old_password(db):
    admin = make_user(db, "root", UserRole.ADMIN)
    target = make_user(db, "erin", UserRole.OPERATOR)
    act_as(admin)

    assert client.post(f"/api/users/{target.id}/reset-password", json={"password": "brand-new-pass-2"}).status_code == 204
    assert client.post(f"/api/users/{target.id}/reset-password", json={"password": "short"}).status_code == 422
    app.dependency_overrides.pop(get_current_active_user)

    assert login("erin", PASSWORD).status_code == 401
    assert login("erin", "brand-new-pass-2").status_code == 200
    assert audit_rows(db, "USER_PASSWORD_RESET")[0].actor == "root"


def test_unknown_user_is_404(db):
    act_as(make_user(db, "root", UserRole.ADMIN))
    assert client.patch("/api/users/9999", json={"is_active": False}).status_code == 404
    assert client.post("/api/users/9999/reset-password", json={"password": PASSWORD}).status_code == 404


def test_user_list_never_exposes_password_hashes(db):
    act_as(make_user(db, "root", UserRole.ADMIN))
    body = client.get("/api/users").text
    assert "hashed_password" not in body and "$2b$" not in body
