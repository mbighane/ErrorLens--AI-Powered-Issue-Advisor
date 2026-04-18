import pytest
from backend.app.main import app

def test_root():
    client = pytest.importorskip("fastapi.testclient").TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "ErrorLens API"}

def test_health():
    client = pytest.importorskip("fastapi.testclient").TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}