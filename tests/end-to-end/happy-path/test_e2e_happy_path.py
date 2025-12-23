import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from typer.testing import CliRunner
import httpx
from pathlib import Path
import json

from imrabo.cli.main import cli_app
from imrabo.cli import core
from imrabo.adapters.http.fastapi_server import app as fastapi_app
from imrabo.kernel.contracts import ExecutionResult, ArtifactHandle
from imrabo.adapters.storage_fs import FileSystemArtifactResolver
from tests.kernel.mocks import MockEngineAdapter, MockArtifactResolver

runner = CliRunner()

# --- Fixtures for E2E setup ---

@pytest.fixture(autouse=True)
def mock_all_runtime_components(tmp_path):
    """
    Mocks all external runtime components for E2E tests:
    - `imrabo.cli.core.RuntimeClient` (to prevent real HTTP calls from CLI during start/stop)
    - `imrabo.cli.core.start_runtime` (to control daemon lifecycle without spawning real process)
    - `imrabo.cli.core.stop_runtime` (to control daemon lifecycle)
    - `imrabo.adapters.http.fastapi_server.kernel` (to control daemon's kernel behavior)
    - `imrabo.internal.paths.get_runtime_pid_file` (to isolate PID files)
    - `imrabo.internal.paths.get_runtime_token_file` (to isolate token files)
    """
    mock_pid_file = tmp_path / "runtime.pid"
    mock_token_file = tmp_path / "runtime.token"
    mock_models_dir = tmp_path / "imrabo_models"

    with patch('imrabo.internal.paths.get_runtime_pid_file', return_value=str(mock_pid_file)), \
         patch('imrabo.internal.paths.get_runtime_token_file', return_value=str(mock_token_file)), \
         patch('imrabo.internal.paths.get_models_dir', return_value=str(mock_models_dir)):
        
        # Mock the RuntimeClient for CLI <-> Daemon communication (core.py)
        with patch('imrabo.cli.core.RuntimeClient', autospec=True) as MockCliRuntimeClient:
            mock_cli_runtime_client_instance = MockCliRuntimeClient.return_value
            mock_cli_runtime_client_instance.health.return_value = {"status": "ok"}
            mock_cli_runtime_client_instance.status.return_value = {"status": "running"}
            mock_cli_runtime_client_instance.shutdown.return_value = {"message": "shutting down"}
            mock_cli_runtime_client_instance.run_prompt.return_value = AsyncMock(return_value=["Mocked output"]).__aiter__()
            
            # Mock the start/stop runtime functions
            with patch('imrabo.cli.core.start_runtime', return_value=True) as mock_start_runtime, \
                 patch('imrabo.cli.core.stop_runtime', return_value=True) as mock_stop_runtime:

                # Mock the kernel within the FastAPI server itself
                mock_fastapi_kernel = MagicMock(spec=MockEngineAdapter) # Use MockEngineAdapter as base for kernel
                mock_fastapi_kernel.get_status.return_value = {"status": "ok_from_kernel"}
                mock_fastapi_kernel.execute.return_value = iter([ # A simple stream
                    ExecutionResult(request_id="test-req", status="streaming", output={"content": "Hello"}, metrics={}),
                    ExecutionResult(request_id="test-req", status="completed", output={"content": ""}, metrics={}),
                ])
                
                with patch('imrabo.adapters.http.fastapi_server.kernel', new=mock_fastapi_kernel) as patched_fastapi_kernel:
                    yield {
                        "mock_pid_file": mock_pid_file,
                        "mock_token_file": mock_token_file,
                        "mock_models_dir": mock_models_dir,
                        "mock_cli_runtime_client": mock_cli_runtime_client_instance,
                        "mock_start_runtime": mock_start_runtime,
                        "mock_stop_runtime": mock_stop_runtime,
                        "mock_fastapi_kernel": patched_fastapi_kernel,
                    }

@pytest.fixture
async def fastapi_test_client():
    """Provides an httpx client for the in-process FastAPI app."""
    async with httpx.AsyncClient(app=fastapi_app, base_url="http://test") as client:
        yield client

# --- Helper function for testing CLI commands ---
def run_cli_command(command_args):
    return runner.invoke(cli_app, command_args)

# --- End-to-End Happy Path Tests ---

def test_fresh_install_run_stop(mock_all_runtime_components, tmp_path):
    """
    Scenario: Fresh installation, start, run inference, then stop.
    """
    # 1. Simulate imrabo install (mocking resolver)
    registry_path = tmp_path / "models.json"
    registry_path.write_text(json.dumps({
        "schema_version": 1,
        "models": {
            "test-model": {
                "id": "test-model", "variants": [{"id": "v1", "files": []}]
            }
        }
    }))
    with patch('imrabo.adapters.storage_fs.FileSystemArtifactResolver', autospec=True) as MockResolver:
        mock_resolver_instance = MockResolver.return_value
        mock_resolver_instance.list_models.return_value = [{"id": "test-model", "variants": [{"id": "v1"}]}]
        mock_resolver_instance._models = {"test-model": {"id": "test-model", "variants": [{"id": "v1"}]}}
        mock_resolver_instance.ensure_available.return_value = ArtifactHandle(
            ref="model:test-model/variant:v1", is_available=True, location=tmp_path / "model.gguf", metadata={}
        )
        install_result = run_cli_command(["install"], input="test-model\nv1\n")
        assert install_result.exit_code == 0
        assert "installed successfully" in install_result.stdout

    # 2. imrabo start
    start_result = run_cli_command(["start"])
    assert start_result.exit_code == 0
    assert "imrabo runtime started successfully" in start_result.stdout
    mock_all_runtime_components["mock_start_runtime"].assert_called_once()

    # 3. imrabo run
    # The run command enters an interactive loop, so we need to provide input
    run_result = runner.invoke(cli_app, ["run"], input="Hello there\n/exit\n")
    assert run_result.exit_code == 0
    assert "imrabo chat started" in run_result.stdout
    assert "Hello" in run_result.stdout # From mock_fastapi_kernel.execute
    mock_all_runtime_components["mock_cli_runtime_client"].run_prompt.assert_called_once()
    assert mock_all_runtime_components["mock_cli_runtime_client"].run_prompt.call_args[0][0] == "Hello there"

    # 4. imrabo stop
    stop_result = run_cli_command(["stop"])
    assert stop_result.exit_code == 0
    assert "imrabo runtime stopped successfully" in stop_result.stdout
    mock_all_runtime_components["mock_stop_runtime"].assert_called_once()


@pytest.mark.asyncio
async def test_daemon_status_reporting(mock_all_runtime_components, fastapi_test_client):
    """
    Test that the daemon's status endpoint correctly reports its state.
    """
    mock_all_runtime_components["mock_fastapi_kernel"].get_status.return_value = {
        "status": "operational",
        "engine_state": "ready",
        "loaded_model": "llama3"
    }
    
    # Send a request directly to the FastAPI app (simulating what CLI client does)
    response = await fastapi_test_client.get("/status", headers={"Authorization": "Bearer mock_token"})
    assert response.status_code == 200
    status_data = response.json()
    assert status_data["status"] == "operational"
    assert status_data["loaded_model"] == "llama3"

    # Also check via CLI, ensuring CLI calls client and client then gets this
    cli_status_result = run_cli_command(["status"])
    assert cli_status_result.exit_code == 0
    assert "operational" in cli_status_result.stdout
    assert "llama3" in cli_status_result.stdout
