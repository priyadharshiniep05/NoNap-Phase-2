import sys
from pathlib import Path

# Add project root and model directory to sys.path
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
_model_dir = str(_project_root / "model")
if _model_dir not in sys.path:
    sys.path.insert(0, _model_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.app.main import app
from server.app.db.auth_db import get_auth_session
from server.app.db.ops_db import get_ops_session
from server.app.db.models_auth import AuthBase, User, Fleet, FleetDriver
from server.app.db.models_ops import OpsBase, Threshold, AlertLog
from server.app.core.security import hash_password, create_access_token

from sqlalchemy.pool import StaticPool
import server.app.db.auth_db as auth_db_module
import server.app.db.ops_db as ops_db_module

# In-memory test SQLite engines with StaticPool so all connections share the DB
TEST_AUTH_URL = "sqlite://"
TEST_OPS_URL = "sqlite://"

test_auth_engine = create_engine(
    TEST_AUTH_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_ops_engine = create_engine(
    TEST_OPS_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestAuthSession = sessionmaker(bind=test_auth_engine, autocommit=False, autoflush=False)
TestOpsSession = sessionmaker(bind=test_ops_engine, autocommit=False, autoflush=False)

# Monkeypatch module-level engines and factories
auth_db_module._auth_engine = test_auth_engine
auth_db_module._AuthSessionLocal = TestAuthSession
ops_db_module._ops_engine = test_ops_engine
ops_db_module._OpsSessionLocal = TestOpsSession


@pytest.fixture(scope="session", autouse=True)
def setup_test_databases():
    """Create all tables in test databases once per test session."""
    AuthBase.metadata.create_all(bind=test_auth_engine)
    OpsBase.metadata.create_all(bind=test_ops_engine)
    yield
    AuthBase.metadata.drop_all(bind=test_auth_engine)
    OpsBase.metadata.drop_all(bind=test_ops_engine)


@pytest.fixture
def auth_db():
    db = TestAuthSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def ops_db():
    db = TestOpsSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(auth_db, ops_db):
    """TestClient with overridden DB session dependencies."""
    def _override_auth_session():
        yield auth_db

    def _override_ops_session():
        yield ops_db

    app.dependency_overrides[get_auth_session] = _override_auth_session
    app.dependency_overrides[get_ops_session] = _override_ops_session

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def test_manager(auth_db):
    """Seed a test fleet manager."""
    mgr = auth_db.query(User).filter(User.email == "test_manager@nonap.demo").first()
    if not mgr:
        mgr = User(
            full_name="Test Manager",
            email="test_manager@nonap.demo",
            password_hash=hash_password("NoNap@123"),
            role="fleet_manager",
            is_active=True,
        )
        auth_db.add(mgr)
        auth_db.commit()
        auth_db.refresh(mgr)

    fleet = auth_db.query(Fleet).filter(Fleet.manager_id == mgr.id).first()
    if not fleet:
        fleet = Fleet(manager_id=mgr.id, name="Test Fleet")
        auth_db.add(fleet)
        auth_db.commit()
        auth_db.refresh(fleet)

    return mgr


@pytest.fixture
def test_driver(auth_db, test_manager):
    """Seed a test driver assigned to test manager's fleet."""
    driver = auth_db.query(User).filter(User.email == "test_driver@nonap.demo").first()
    if not driver:
        driver = User(
            full_name="Test Driver",
            email="test_driver@nonap.demo",
            password_hash=hash_password("NoNap@123"),
            role="driver",
            is_active=True,
        )
        auth_db.add(driver)
        auth_db.commit()
        auth_db.refresh(driver)

    fleet = auth_db.query(Fleet).filter(Fleet.manager_id == test_manager.id).first()
    fd = auth_db.query(FleetDriver).filter(
        FleetDriver.fleet_id == fleet.id, FleetDriver.driver_id == driver.id
    ).first()
    if not fd:
        fd = FleetDriver(fleet_id=fleet.id, driver_id=driver.id)
        auth_db.add(fd)
        auth_db.commit()

    return driver


@pytest.fixture
def manager_token(test_manager):
    return create_access_token(user_id=test_manager.id, role="fleet_manager")


@pytest.fixture
def driver_token(test_driver):
    return create_access_token(user_id=test_driver.id, role="driver")


@pytest.fixture
def manager_headers(manager_token):
    return {"Authorization": f"Bearer {manager_token}"}


@pytest.fixture
def driver_headers(driver_token):
    return {"Authorization": f"Bearer {driver_token}"}
