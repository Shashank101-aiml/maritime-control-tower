"""FastAPI's database dependency. The engine itself lives in app.database.connection."""

from app.database.connection import SessionLocal, engine, get_db  # noqa: F401
