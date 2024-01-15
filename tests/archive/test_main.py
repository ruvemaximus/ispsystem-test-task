import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_root():
    with TestClient(app=app) as client:
        response = client.get('/')
    assert response.status_code == 404
