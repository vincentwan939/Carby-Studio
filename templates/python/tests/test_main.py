"""Tests for main application."""

import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """Test health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "service" in data


def test_root_endpoint(client: TestClient):
    """Test root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


# TODO: Add your tests here
# Example:
# def test_create_user(client: TestClient):
#     """Test creating a new user."""
#     response = client.post("/users/", json={"email": "test@example.com"})
#     assert response.status_code == 201
#     assert response.json()["email"] == "test@example.com"
