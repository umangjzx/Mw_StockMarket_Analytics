"""
Pytest fixtures for unit and integration tests.

Unit tests mock all external dependencies (DB, Redis, external APIs).
Integration tests use testcontainers for real Postgres + Redis instances.
"""

import asyncio
from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app():
    """Return the FastAPI app instance with CELERY_TASK_ALWAYS_EAGER=True."""
    import os
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["SECRET_KEY"] = "test-secret-key"
    from app.main import create_app
    return create_app()


@pytest.fixture
def client(app) -> TestClient:
    """Synchronous test client for simple request/response tests."""
    return TestClient(app)


@pytest.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for async endpoint tests."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
