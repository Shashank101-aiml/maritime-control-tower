"""Set or change an account's password without going through the web UI.

    python -m app.cli.set_password admin
    docker compose exec backend python -m app.cli.set_password admin

The password is typed at a hidden prompt, so it never lands in shell history
or a config file."""

import getpass
import sys

from app.core.passwords import check_password_strength
from app.core.security import hash_password
from app.database.session import SessionLocal
from app.governance.audit import log_audit_event
from app.models.user import User


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: python -m app.cli.set_password <username>")
        return 2
    username = argv[1]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            print(f"No account named '{username}'.")
            return 1
        password = getpass.getpass(f"New password for {username}: ")
        problem = check_password_strength(password, username)
        if problem:
            print(f"That password {problem}.")
            return 1
        if getpass.getpass("Type it again: ") != password:
            print("The two entries differ; nothing changed.")
            return 1
        user.hashed_password = hash_password(password)
        db.commit()
        log_audit_event(
            db, "USER_PASSWORD_RESET", None, None, "command-line", f"USER:{username}", "RESET_PASSWORD",
            "OK", f"Password for {username} was set from the command line",
        )
        print(f"Password for {username} updated.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
