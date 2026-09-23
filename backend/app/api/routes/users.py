"""Admin-only user management: list, create, change role / active state,
and reset a password.

Every change is written to the audit log with the acting admin's username.
A guard rail stops an admin locking everyone out: you cannot change your own
role or deactivate yourself, so the admin making a change always remains an
active admin.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_active_superuser
from app.api.dependencies.database import get_db
from app.core.constants import UserRole
from app.core.security import hash_password
from app.governance.audit import log_audit_event
from app.models.user import User

router = APIRouter()

MIN_PASSWORD_LENGTH = 8


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(max_length=256, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: Optional[str] = Field(default=None, max_length=128)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    role: UserRole = UserRole.OPERATOR


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=128)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


def _is_admin(user: User) -> bool:
    return user.is_superuser or user.role == UserRole.ADMIN


def _get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _apply_role(user: User, role: UserRole) -> None:
    # The superuser flag and the admin role always move together.
    user.role = role
    user.is_superuser = role == UserRole.ADMIN


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_active_superuser),
):
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_active_superuser),
):
    username = payload.username.strip()
    email = payload.email.strip().lower()
    clash = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if clash is not None:
        field = "username" if clash.username == username else "email"
        raise HTTPException(status_code=409, detail=f"That {field} is already in use")

    user = User(
        username=username,
        email=email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        is_active=True,
    )
    _apply_role(user, payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)

    log_audit_event(
        db, "USER_CREATED", None, None, admin.username, f"USER:{user.username}", "CREATE",
        payload.role.value, f"{admin.username} created {user.username} with role {payload.role.value}",
    )
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_active_superuser),
):
    user = _get_user(db, user_id)
    changes = []

    new_role = payload.role
    role_changes = new_role is not None and new_role != (UserRole.ADMIN if _is_admin(user) else UserRole(user.role))
    deactivates = payload.is_active is False and user.is_active

    if user.id == admin.id and (role_changes or deactivates):
        raise HTTPException(status_code=400, detail="You cannot change your own role or deactivate yourself")

    if role_changes:
        changes.append(f"role {UserRole(user.role).value} -> {new_role.value}")
        _apply_role(user, new_role)
    if payload.is_active is not None and payload.is_active != user.is_active:
        changes.append("activated" if payload.is_active else "deactivated")
        user.is_active = payload.is_active
    if payload.full_name is not None and payload.full_name != user.full_name:
        changes.append("name updated")
        user.full_name = payload.full_name

    if changes:
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        log_audit_event(
            db, "USER_UPDATED", None, None, admin.username, f"USER:{user.username}", "UPDATE",
            "OK", f"{admin.username} changed {user.username}: {', '.join(changes)}",
        )
    return user


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    payload: PasswordReset,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_active_superuser),
):
    user = _get_user(db, user_id)
    user.hashed_password = hash_password(payload.password)
    user.updated_at = datetime.utcnow()
    db.commit()
    log_audit_event(
        db, "USER_PASSWORD_RESET", None, None, admin.username, f"USER:{user.username}", "RESET_PASSWORD",
        "OK", f"{admin.username} reset the password for {user.username}",
    )
