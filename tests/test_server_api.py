import pytest
from fastapi.testclient import TestClient
from skybrain.server.app import app


def test_healthz_endpoint():
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "active_model" in data


def test_models_list_endpoint():
    client = TestClient(app)
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 2


def test_system_environment_endpoint():
    client = TestClient(app)
    resp = client.get("/v1/system/environment")
    assert resp.status_code == 200
    data = resp.json()
    assert "tier" in data
    assert "title" in data
    assert "message" in data
    assert "allowed" in data



def test_system_memory_endpoint():
    client = TestClient(app)
    resp = client.get("/v1/system/memory")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_gb" in data
    assert "available_gb" in data

