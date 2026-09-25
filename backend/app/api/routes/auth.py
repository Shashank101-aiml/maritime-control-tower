from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_active_user
from app.api.dependencies.database import get_db
from app.core import login_guard
from app.core.security import create_access_token, verify_password
from app.models.user import User

router = APIRouter()


@router.post("/auth/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2 password flow. `username` accepts either username or email.

    Failures return the same message whether the account is missing or
    the password is wrong, so the endpoint cannot be used to enumerate
    valid accounts.
    """
    identifier = form_data.username.strip()
    address = request.client.host if request.client else "unknown"
    wait = login_guard.seconds_until_allowed(address, identifier)
    if wait is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed sign-in attempts. Try again in {max(1, wait // 60)} minute(s).",
            headers={"Retry-After": str(wait)},
        )
    user = (
        db.query(User)
        .filter((User.username == identifier) | (User.email == identifier))
        .first()
    )

    if user is None or not verify_password(form_data.password, user.hashed_password):
        login_guard.record_failure(address, identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_guard.record_success(address, identifier)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is disabled",
        )

    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
            "is_superuser": user.is_superuser,
        },
    }


@router.get("/auth/me")
def read_current_user(current_user: User = Depends(get_current_active_user)):
    """Lets the frontend validate a stored token on load."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value if hasattr(current_user.role, "value") else current_user.role,
        "is_superuser": current_user.is_superuser,
    }
