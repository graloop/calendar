# Shared test setup: a throwaway data folder, a fresh database for each test,
# and a client that talks to the app without starting a server.
# Only fake courses here (ABC123, XYZ789...): never real ones.

import os
import tempfile

# Configure the app before it's imported: settings and the engine are read at
# module import time.
_TMP_DIR = tempfile.mkdtemp(prefix="agenda-tests-")
os.environ["DATA_DIR"] = _TMP_DIR

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def fresh_data():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def add_event(client, **fields):
    """Adds an event (a lab on Tue Nov 24, 2026 unless told otherwise) and answers it."""
    body = {"title": "Lab 3", "type": "lab", "course": "ABC123", "date": "2026-11-24", **fields}
    response = client.post("/api/events", json=body)
    assert response.status_code == 201, response.text
    return response.json()
