#!/usr/bin/env python3
"""First-time setup for a fresh clone: creates .env with generated secrets.

    python scripts/bootstrap.py

Uses only the standard library, so it runs before anything is installed.
It never overwrites an existing .env. The generated admin password is shown
once on screen and stored only in your local .env, which git ignores.
"""

import os
import re
import secrets
import shutil
import string
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"


def strong_password(length: int = 18) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw):
            return pw


def set_value(text: str, key: str, value: str) -> str:
    return re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.M)


def get_value(text: str, key: str) -> str:
    match = re.search(rf"^{key}=(.*)$", text, flags=re.M)
    return match.group(1).strip() if match else ""


def check_existing() -> int:
    text = ENV.read_text(encoding="utf-8")
    problems = []
    if len(get_value(text, "SECRET_KEY")) < 32:
        problems.append("SECRET_KEY is missing or shorter than 32 characters")
    if len(get_value(text, "FIRST_SUPERUSER_PASSWORD")) < 12:
        problems.append("FIRST_SUPERUSER_PASSWORD is missing or shorter than 12 characters")
    if not get_value(text, "POSTGRES_PASSWORD"):
        problems.append("POSTGRES_PASSWORD is empty")
    if problems:
        print(".env already exists but needs attention:")
        for p in problems:
            print(f"  - {p}")
        print("Fix those lines by hand, or delete .env and run this again.")
        return 1
    print(".env already exists and looks fine; nothing changed.")
    return 0


def main() -> int:
    print("Maritime Control System - first-time setup\n")
    if ENV.exists():
        code = check_existing()
    else:
        text = EXAMPLE.read_text(encoding="utf-8")
        admin_password = strong_password()
        text = set_value(text, "SECRET_KEY", secrets.token_urlsafe(48))
        text = set_value(text, "POSTGRES_PASSWORD", strong_password(24))
        text = set_value(text, "FIRST_SUPERUSER_PASSWORD", admin_password)
        # Docker Compose talks to the db service and overrides this; a native run uses it.
        ENV.write_text(text, encoding="utf-8")
        try:
            os.chmod(ENV, 0o600)  # owner-only where the OS supports it
        except OSError:
            pass
        print("Created .env with freshly generated secrets.\n")
        print("  Sign in at the app with:")
        print(f"    username: {get_value(text, 'FIRST_SUPERUSER_USERNAME')}")
        print(f"    password: {admin_password}")
        print("  This is shown once here and stored only in your local .env (never committed).")
        print("  Change it after first sign-in: docker compose exec backend python -m app.cli.set_password admin\n")
        print("  Optional API keys (AISSTREAM_API_KEY, OIL_PRICE_API, ...) are blank in .env; the")
        print("  matching features stay off until you add your own keys. Never share or commit .env.\n")
        code = 0

    if code == 0:
        docker = shutil.which("docker")
        if docker is None:
            print("Docker was not found. Install Docker Desktop, or follow 'Run without Docker' in README.md.")
        else:
            ok = subprocess.run([docker, "info"], capture_output=True).returncode == 0
            print("Docker is running." if ok else "Docker is installed but not running; start Docker Desktop first.")
        print("\nNext:  docker compose up -d --build     then open http://localhost")
    return code


if __name__ == "__main__":
    sys.exit(main())
