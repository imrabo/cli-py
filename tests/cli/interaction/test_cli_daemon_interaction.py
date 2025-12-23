import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch, AsyncMock
import httpx
import asyncio
from imrabo.cli.main import cli_app
from imrabo.cli.client import RuntimeClient

runner = CliRunner()

# --- Fixtures for Mocking RuntimeClient ---
@pytest.fixture
def mock_runtime_client():
    """Provides a mocked RuntimeClient instance."""
    with patch('imrabo.cli.client.RuntimeClient', autospec=True) as MockClient:
        instance = MockClient.return_value
        yield instance

# --- Tests for Daemon Not Running ---
def test_cli_status_daemon_not_running(mock_runtime_client):
    """
    Test 'imrabo status' when daemon is not running (connection error).
    """
    mock_runtime_client.status.side_effect = httpx.ConnectError("Connection refused")
    result = runner.invoke(cli_app, ["status"])

    assert result.exit_code == 1
    assert "Could not connect to imrabo runtime. Is it running?" in result.stdout
    assert mock_runtime_client.status.called

def test_cli_run_daemon_not_running_attempts_start(mock_runtime_client):
    """
    Test 'imrabo run' attempts to start daemon if not running.
    """
    mock_runtime_client.health.return_value = {"status": "ok"} # After start, it's healthy
    mock_runtime_client.run_prompt.return_value = AsyncMock(return_value=["Mocked output"])
    
    with patch('imrabo.cli.core.start_runtime', return_value=True) as mock_start_runtime, \
         patch('imrabo.cli.core.is_runtime_active', side_effect=[False, True]): # First check False, then True after start
        
        # Simulate interactive input for the run command
        result = runner.invoke(cli_app, ["run"], input="/exit")

        assert "Starting runtime..." in result.stdout
        mock_start_runtime.assert_called_once()
        assert result.exit_code == 0
        assert "Goodbye." in result.stdout # Confirms it reached the /exit part

def test_cli_run_daemon_start_fails(mock_runtime_client):
    """
    Test 'imrabo run' handles daemon start failure.
    """
    with patch('imrabo.cli.core.start_runtime', return_value=False) as mock_start_runtime, \
         patch('imrabo.cli.core.is_runtime_active', return_value=False):
        
        result = runner.invoke(cli_app, ["run"])

        assert "Starting runtime..." in result.stdout
        assert "Failed to start runtime" in result.stdout
        mock_start_runtime.assert_called_once()
        assert result.exit_code == 1

# --- Tests for Auth Token Mismatch ---
def test_cli_run_auth_token_mismatch(mock_runtime_client):
    """
    Test 'imrabo run' when daemon returns 401 Unauthorized.
    """
    mock_runtime_client.health.return_value = {"status": "ok"} # Assume daemon is up
    mock_runtime_client.run_prompt.side_effect = httpx.HTTPStatusError(
        "Unauthorized", request=httpx.Request("POST", "/run"), response=httpx.Response(401)
    )

    with patch('imrabo.cli.core.is_runtime_active', return_value=True):
        result = runner.invoke(cli_app, ["run"], input="test prompt\n/exit")
        
        assert "Error during prompt execution: HTTPStatusError('Unauthorized')" in result.stdout
        assert result.exit_code == 0 # User can still exit cleanly even if command failed

# --- Tests for Network Interruption during Streaming ---
def test_cli_run_network_interruption_during_stream(mock_runtime_client):
    """
    Test 'imrabo run' handles network interruption during streaming.
    """
    # Mock health check to pass initially
    mock_runtime_client.health.return_value = {"status": "ok"} 

    # Mock run_prompt to yield some data, then raise an error
    async def mock_streaming_error():
        yield "Part 1 "
        yield "Part 2 "
        raise httpx.ConnectError("Network dropped")
    mock_runtime_client.run_prompt.return_value = mock_streaming_error().__aiter__()

    with patch('imrabo.cli.core.is_runtime_active', return_value=True):
        result = runner.invoke(cli_app, ["run"], input="test prompt\n/exit")

        assert "Part 1 Part 2 " in result.stdout
        assert "Error during prompt execution: ConnectError('Network dropped')" in result.stdout
        assert result.exit_code == 0 # User can exit
