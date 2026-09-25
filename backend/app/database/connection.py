"""The one database engine and session factory for the whole app.

`app.api.dependencies.database` and `app.database.session` re-export these,
so there is exactly one engine. (There used to be two copies, and this one
crashed on any non-SQLite URL because it handed SQLAlchemy a pydantic URL
object instead of a string.)"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

_url = str(settings.DATABASE_URL)

engine = create_engine(_url, connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
