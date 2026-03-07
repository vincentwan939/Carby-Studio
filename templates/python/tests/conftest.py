"""pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


# TODO: Add your fixtures here
# @pytest.fixture
# def db_session():
#     """Create a test database session."""
#     # Setup test database
#     yield session
#     # Teardown
