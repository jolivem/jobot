import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force sqlite for tests
os.environ["DB_URL_OVERRIDE"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = os.environ.get("JWT_SECRET", "test_secret_change_me")

from app.main import create_app
from app.core.db import Base
from app.core.db import get_db as get_db_dep

@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture()
def client(db_session):
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_dep] = override_get_db
    return TestClient(app)

def register_user(client: TestClient, email: str, password: str):
    return client.post("/auth/register", json={"email": email, "password": password})

def login_user(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})
