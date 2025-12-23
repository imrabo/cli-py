import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os
import secrets
import httpx

from imrabo.adapters.http.fastapi_server import app
from imrabo.cli.client import RuntimeClient, load_token, generate_token, save_token # Also test these functions directly
from imrabo.internal import paths


# --- Fixtures ---

@pytest.fixture
def temp_token_file(tmp_path):
    """Fixture to ensure a clean token file path for each test."""
    original_get_runtime_token_file = paths.get_runtime_token_file
    mock_token_file_path = tmp_path / "runtime.token"
    paths.get_runtime_token_file = lambda: str(mock_token_file_path)
    yield mock_token_file_path
    paths.get_runtime_token_file = original_get_runtime_token_file
    if mock_token_file_path.exists():
        mock_token_file_path.unlink()

@pytest.fixture
async def async_client_security():
    """Asynchronous test client for the FastAPI app for security tests."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

# --- Security Tests: Auth Token Management ---

def test_load_token_nonexistent_file(temp_token_file):
    """Test loading token from a nonexistent file."""
    assert load_token(temp_token_file) is None

def test_save_and_load_token(temp_token_file):
    """Test saving and loading a token."""
    test_token = secrets.token_urlsafe(32)
    save_token(test_token, temp_token_file)
    assert temp_token_file.exists()
    assert load_token(temp_token_file) == test_token

def test_generate_token_produces_valid_string():
    """Test that generate_token produces a non-empty string."""
    token = generate_token()
    assert isinstance(token, str)
    assert len(token) > 20 # Typical length for urlsafe token

# --- Security Tests: FastAPI Adapter Authentication ---

@pytest.mark.asyncio
async def test_fastapi_adapter_rejects_no_token(async_client_security):
    """Test that FastAPI adapter rejects requests with no Authorization header."""
    response = await async_client_security.get("/health")
    assert response.status_code == 401
    assert "detail" in response.json()
    assert response.json()["detail"] == "Not authenticated" # FastAPI default

@pytest.mark.asyncio
async def test_fastapi_adapter_rejects_invalid_token(async_client_security, temp_token_file):
    """Test that FastAPI adapter rejects requests with an invalid token."""
    # Ensure a valid token is set in the runtime for comparison
    valid_token = secrets.token_urlsafe(32)
    save_token(valid_token, temp_token_file)
    
    # Patch the global RUNTIME_AUTH_TOKEN in fastapi_server.py
    with patch('imrabo.adapters.http.fastapi_server.RUNTIME_AUTH_TOKEN', valid_token):
        headers = {"Authorization": "Bearer invalid_token"}
        response = await async_client_security.get("/health", headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication credentials"

@pytest.mark.asyncio
async def test_fastapi_adapter_accepts_valid_token(async_client_security, temp_token_file):
    """Test that FastAPI adapter accepts requests with a valid token."""
    valid_token = secrets.token_urlsafe(32)
    save_token(valid_token, temp_token_file)

    with patch('imrabo.adapters.http.fastapi_server.RUNTIME_AUTH_TOKEN', valid_token):
        headers = {"Authorization": f"Bearer {valid_token}"}
        response = await async_client_security.get("/health", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_runtime_client_sends_correct_token(async_client_security, temp_token_file):
    """Test that RuntimeClient correctly loads and sends the token."""
    test_token = secrets.token_urlsafe(32)
    save_token(test_token, temp_token_file)
    
    with patch('imrabo.adapters.http.fastapi_server.RUNTIME_AUTH_TOKEN', test_token):
        client = RuntimeClient(host="test", port=80) # Use dummy host/port for test client
        response = await client.health()
        assert response["status"] == "ok"
