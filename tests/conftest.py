import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """Geteiltes TestClient-Fixture mit temporärer Datenbank."""
    db_path = tmp_path / "test.db"

    with patch("src.storage.database.DB_PATH", db_path), \
         patch("src.scheduler.start_scheduler"), \
         patch("src.scheduler.stop_scheduler"):

        from src.main import app

        with TestClient(app) as c:
            yield c
