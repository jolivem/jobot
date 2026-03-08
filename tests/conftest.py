import os
import pytest
from fastapi.testclient import TestClient

# Force sqlite for tests — must be set before any app imports
os.environ["DB_URL_OVERRIDE"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = os.environ.get("JWT_SECRET", "test_secret_change_me")

import app.models  # noqa: F401 — register all models with Base.metadata
from app.main import create_app
from app.core.db import Base, engine, SessionLocal
from app.core.db import get_db as get_db_dep


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    app = create_app()

    # Disable rate limiting in tests
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    app.state.limiter = Limiter(key_func=get_remote_address, enabled=False)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_dep] = override_get_db
    return TestClient(app)

def register_user(client: TestClient, email: str, password: str):
    r = client.post("/auth/register", json={"email": email, "password": password})
    if r.status_code == 200:
        # Auto-verify user so login works in tests
        user_id = r.json()["id"]
        from app.models.user import User
        db = SessionLocal()
        db.query(User).filter(User.id == user_id).update({"is_verified": True})
        db.commit()
        db.close()
    return r

def login_user(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})
