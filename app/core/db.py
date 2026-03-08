from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

class Base(DeclarativeBase):
    pass

def _make_engine():
    url = settings.db_url
    if url.startswith("sqlite"):
        # For unit tests: StaticPool ensures a single shared connection
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=10,
        max_overflow=20,
    )

engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
