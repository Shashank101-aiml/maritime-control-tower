from typing import Generator

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal, engine
from app.database.base import Base


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()