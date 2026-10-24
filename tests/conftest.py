import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import engine, Base, SessionLocal, init_db
from app.models.tenant import Tenant


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Ensure pgvector extension is created and all tables are initialized."""
    init_db()
    yield


@pytest.fixture
def db_session():
    """Provides a fresh transactional session for test verification."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture
def test_tenant(db_session: Session):
    """Creates an isolated test tenant for tests."""
    tenant = Tenant(
        name=f"Test Robotics Org {uuid.uuid4().hex[:6]}",
        slug=f"robotics-{uuid.uuid4().hex[:8]}",
        plan_tier="ENTERPRISE",
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant
