import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient

# Ensure backend and product root are on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import init_db, get_engine, SessionLocal, Base
from app.main import app
from app.adapters.simulation import simulation_adapter


@pytest.fixture
def test_db_url():
    """Isolated temporary SQLite database for each test run."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_shadowlink.db")
    url = f"sqlite:///{db_path}"
    engine = get_engine(url)
    init_db(engine)
    simulation_adapter.reset()
    yield url
    simulation_adapter.reset()
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
        wal = f"{db_path}-wal"
        shm = f"{db_path}-shm"
        if os.path.exists(wal):
            os.remove(wal)
        if os.path.exists(shm):
            os.remove(shm)
        os.rmdir(temp_dir)
    except Exception:
        pass


@pytest.fixture
def client():
    """FastAPI test client."""
    init_db()
    simulation_adapter.reset()
    with TestClient(app) as c:
        yield c
    simulation_adapter.reset()
