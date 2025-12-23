import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from typer.testing import CliRunner
import httpx
from pathlib import Path
import json
import shutil
import os
import random
import signal

from imrabo.cli.main import cli_app
from imrabo.cli import core
from imrabo.adapters.http.fastapi_server import app as fastapi_app
from imrabo.kernel.contracts import ExecutionResult, ArtifactHandle
from imrabo.adapters.storage_fs import FileSystemArtifactResolver
from tests.kernel.mocks import MockEngineAdapter, MockArtifactResolver # Re-use mocks
from tests.end_to_end.happy_path.test_e2e_happy_path import run_cli_command, mock_all_runtime_components, fastapi_test_client # Re-use fixtures


# --- Fixtures for Hostile Environment ---

@pytest.fixture
def mock_random_process_kill(mocker):
    """
    Mocks os.kill to randomly kill the mocked daemon process during a critical phase.
    """
    original_os_kill = os.kill
    def flaky_kill(pid, sig):
        if sig == signal.SIGTERM and random.random() < 0.5: # 50% chance to kill
            raise ProcessLookupError("Simulating process already dead") # Process terminated
        original_os_kill(pid, sig)

    mocker.patch('os.kill', side_effect=flaky_kill)
    yield


@pytest.fixture
def mock_corrupted_pid_file(mock_all_runtime_components):
    """Corrupts the PID file before starting tests."""
    pid_file = mock_all_runtime_components["mock_pid_file"]
    pid_file.write_text("malformed_pid_content")
    yield


@pytest.fixture
def mock_engine_outputs_malformed_json(mock_all_runtime_components):
    """
    Configures the mock FastAPI kernel to return malformed JSON from engine.
    """
    mock_all_runtime_components["mock_fastapi_kernel"].execute.return_value = iter([
        ExecutionResult(request_id="malformed-req", status="streaming", output={"content": "Good part"}, metrics={}),
        ExecutionResult(request_id="malformed-req", status="streaming", output="NOT JSON STRING", metrics={}), # Bad output
        ExecutionResult(request_id="malformed-req", status="completed", output={"content": ""}, metrics={}),
    ])
    yield


# --- End-to-End Hostile Environment Tests ---

def test_cli_daemon_recovers_from_random_kill_during_stop(mock_all_runtime_components, mock_random_process_kill):
    """
    Test that the CLI's stop command gracefully handles the daemon being
    randomly killed during the stop sequence.
    """
    # Simulate a PID file existing, so core.stop_runtime attempts to kill
    mock_all_runtime_components["mock_pid_file"].write_text("12345") # Dummy PID

    stop_result = run_cli_command(["stop"])
    
    # We expect the stop command to either succeed (if kill worked) or report an error
    # but not crash the CLI.
    assert stop_result.exit_code == 0 or stop_result.exit_code == 1
    assert "stopped successfully" in stop_result.stdout or "Error: Failed to stop" in stop_result.stdout
    
    # Crucially, the PID file should be gone regardless of os.kill outcome
    assert not mock_all_runtime_components["mock_pid_file"].exists()


def test_daemon_starts_with_corrupted_pid_file(mock_all_runtime_components, mock_corrupted_pid_file):
    """
    Test that the daemon's start command can handle a corrupted PID file,
    clean it up, and proceed with starting.
    """
    # Core.start_runtime is mocked to assume success, so we primarily test the cleanup
    start_result = run_cli_command(["start"])
    
    assert start_result.exit_code == 0
    assert "imrabo runtime started successfully" in start_result.stdout
    assert mock_all_runtime_components["mock_pid_file"].exists() # New PID written
    assert mock_all_runtime_components["mock_pid_file"].read_text() != "malformed_pid_content" # Old content removed


@pytest.mark.asyncio
async def test_run_malformed_engine_output(mock_all_runtime_components, mock_engine_outputs_malformed_json):
    """
    Test that 'imrabo run' handles malformed output from the engine adapter gracefully.
    """
    run_result = run_cli_command(["run"], input="malformed_test\n/exit\n")
    
    assert run_result.exit_code == 0
    assert "Good part" in run_result.stdout
    # The malformed part should ideally be logged/handled but not crash the client
    # Since our fastapi_server currently only extracts 'content' and 'stop',
    # if the output field is not a dict it will result in an error for the client
    # or the json.loads will fail in the cli client side
    assert "Error during prompt execution" in run_result.stdout # FastAPI adapter will propagate error if it cannot handle malformed output

# Further hostile tests could include:
# - Simulating disk corruption during model install
# - Mocking network partition between daemon and engine
# - Sending invalid HTTP requests directly to FastAPI adapter with malformed JSON
# - Testing plugin security against attempts to access forbidden resources (requires full plugin system)
