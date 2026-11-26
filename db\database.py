"""Database engine: PostgreSQL via DATABASE_URL (Neon / Supabase / Cloud SQL) or local SQLite fallback."""
import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _url():
    is_serverless = bool(os.environ.get("K_SERVICE") or os.environ.get("VERCEL"))
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):
            return "postgresql+psycopg2://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg2://" + url[len("postgresql://"):]
        # On read-only serverless filesystems (Vercel / Cloud Run), force SQLite into /tmp
        if is_serverless and url.startswith("sqlite") and "/tmp/" not in url and ":memory:" not in url:
            return "sqlite:////tmp/admissions.db"
        return url
    # Cloud Run and Vercel have a read-only app dir; /tmp is writable (ephemeral!) - use Postgres in production.
    path = "/tmp/admissions.db" if is_serverless else os.path.join(ROOT, "admissions.db")
    return "sqlite:///" + path


DATABASE_URL = _url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_size=int(os.environ.get("DB_POOL_SIZE", 5)), max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", 5)),
                           pool_pre_ping=True, pool_recycle=1800)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def backend_name():
    return "sqlite" if IS_SQLITE else "postgresql"
