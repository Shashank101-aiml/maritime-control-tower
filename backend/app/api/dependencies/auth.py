"""Authentication dependencies.

The previous version of this module imported `app.crud` and
`app.api.dependencies.db`, neither of which exist in this codebase, so
it raised ImportError and no route could ever have depended on it.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.core.constants import UserRole
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    subject: Optional[str] = decode_access_token(token)
    if subject is None:
        raise CREDENTIALS_EXCEPTION

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise CREDENTIALS_EXCEPTION

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise CREDENTIALS_EXCEPTION
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


# Higher rank includes every permission of the ranks below it.
ROLE_RANK = {UserRole.OPERATOR: 1, UserRole.SUPERVISOR: 2, UserRole.ADMIN: 3}


def effective_role(user: User) -> UserRole:
    """The superuser flag always means admin, even if `role` was left at its
    default -- so an account can never hold admin power without the role."""
    if user.is_superuser:
        return UserRole.ADMIN
    try:
        return UserRole(user.role)
    except ValueError:
        return UserRole.OPERATOR


def require_role(minimum: UserRole):
    """Dependency factory: 403 unless the signed-in user's role is at least
    `minimum` (operator < supervisor < admin)."""

    def dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if ROLE_RANK[effective_role(current_user)] < ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires the {minimum.value} role or higher",
            )
        return current_user

    return dependency


def get_current_active_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Admin-only: quarantining agents and managing users."""
    if effective_role(current_user) != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires the admin role",
        )
    return current_user
