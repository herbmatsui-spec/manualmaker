"""
Unit Tests for Web API and Phase 2 Endpoints
"""

import pytest
from fastapi.testclient import TestClient

from src.web.app import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_public_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "gemini_model_name" in data
    assert "web_upload_max_mb" in data


def test_upload_invalid_file_extension():
    response = client.post(
        "/api/upload",
        files={"file": ("test.txt", b"dummy content", "text/plain")}
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_mermaid_validate_valid():
    response = client.post(
        "/api/mermaid/validate",
        json={"mermaid_code": "graph TD;\n  A-->B;"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["type"] == "graph"


def test_mermaid_validate_empty():
    response = client.post(
        "/api/mermaid/validate",
        json={"mermaid_code": "   "}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
