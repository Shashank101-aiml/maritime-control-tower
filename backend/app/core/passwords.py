"""Password policy for accounts the system creates itself (the first admin
and the reset command). Kept separate from hashing so it can be reused."""

from typing import Optional

MIN_LENGTH = 12
COMMON = {
    "admin", "administrator", "password", "password1", "passw0rd", "changeme", "change-me",
    "letmein", "welcome", "qwerty", "123456", "12345678", "123456789", "1234567890",
    "admin123", "adminadmin", "administrator1", "maritime", "maritime123",
}


def check_password_strength(password: str, username: Optional[str] = None) -> Optional[str]:
    """None if the password is acceptable, otherwise the reason it is not."""
    if len(password) < MIN_LENGTH:
        return f"must be at least {MIN_LENGTH} characters"
    lowered = password.lower()
    if lowered in COMMON or lowered.startswith("change-me"):
        return "is a well-known password"
    if username and username.lower() in lowered:
        return "must not contain the username"
    if len(set(password)) < 5:
        return "is too repetitive"
    return None
