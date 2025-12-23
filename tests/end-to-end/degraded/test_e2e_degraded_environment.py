import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from typer.testing import CliRunner
import httpx
from pathlib import Path
import json
import shutil
import time
import random

from imrabo.cli.main import cli_app
from imrabo.cli import core
from imrabo.adapters.http.fastapi_server import app as fastapi_app
from imrabo.kernel.contracts import ExecutionResult, ArtifactHandle
from imrabo.adapters.storage_fs import FileSystemArtifactResolver
from tests.kernel.mocks import MockEngineAdapter, MockArtifactResolver # Re-use mocks
from tests.end_to_end.happy_path.test_e2e_happy_path import run_cli_command, mock_all_runtime_components, fastapi_test_client # Re-use fixtures


# --- Fixtures for Degraded Environment ---

@pytest.fixture
def mock_disk_usage_low(mocker):
    """Mocks shutil.disk_usage to report low disk space."""
    # (total, used, free) in bytes
    mocker.patch('shutil.disk_usage', return_value=(100 * 1024**3, 99 * 1024**3, 1 * 1024**3)) # 1GB free
    yield

@pytest.fixture
def mock_requests_slow(mocker):
    """Mocks requests.get and requests.post to introduce delays."""
    mocker.patch('requests.get', side_effect=lambda *args, **kwargs: time.sleep(0.5) or MagicMock(status_code=200, json=lambda: {"status": "ok"}, raise_for_status=lambda: None))
    mocker.patch('requests.post', side_effect=lambda *args, **kwargs: time.sleep(0.8) or MagicMock(status_code=200, iter_lines=lambda: [b'data: {"content": "Slow", "stop": true}'], raise_for_status=lambda: None))
    yield

@pytest.fixture
def mock_engine_intermittent_fail(mock_engine_adapter_for_fastapi):
    """
    Mocks the engine adapter within the FastAPI kernel to occasionally fail execution.
    """
    original_execute = mock_engine_adapter_for_fastapi.execute

    def flaky_execute(request):
        if random.random() < 0.3: # 30% chance to fail
            raise RuntimeError("Intermittent engine failure!")
        return original_execute(request) # Call original mock behavior
    
    mock_engine_adapter_for_fastapi.execute.side_effect = flaky_execute
    yield

# --- End-to-End Degraded Environment Tests ---

def test_install_low_disk_space_fails_gracefully(mock_all_runtime_components, mock_disk_usage_low):
    """
    Test that 'imrabo install' fails gracefully when disk space is low.
    """
    # Override ensure_available for this test to not try actual download
    with patch.object(FileSystemArtifactResolver, 'ensure_available', side_effect=RuntimeError("Insufficient disk space")) as mock_ensure_available:
        # Mock install resolver for this test.
        # This requires adjusting the mock setup in mock_all_runtime_components or creating a specific one.
        # For now, this test will target the error message from the CLI.
        install_result = run_cli_command(["install"], input="test-model\nv1\n")

        assert install_result.exit_code == 1
        assert "Installation failed: Insufficient disk space" in install_result.stdout
        mock_ensure_available.assert_called_once()

@pytest.mark.asyncio
async def test_run_slow_engine_degrades_gracefully(mock_all_runtime_components, mock_requests_slow):
    """
    Test that 'imrabo run' operates with degraded performance but still functions
    when the engine is slow.
    """
    # The mock_requests_slow will cause internal httpx calls to sleep
    # We still need the kernel mock to provide streamable results to the client
    mock_all_runtime_components["mock_fastapi_kernel"].execute.return_value = iter([
        ExecutionResult(request_id="req-slow", status="streaming", output={"content": "Slowly"}, metrics={}),
        ExecutionResult(request_id="req-slow", status="streaming", output={"content": "yielding"}, metrics={}),
        ExecutionResult(request_id="req-slow", status="completed", output={"content": ""}, metrics={}),
    ])
    
    start_time = time.time()
    run_result = run_cli_command(["run"], input="long_prompt\n/exit\n")
    end_time = time.time()
    
    assert run_result.exit_code == 0
    assert "Slowlyyielding" in run_result.stdout
    assert (end_time - start_time) > 1.0 # Should be noticeably slower due to mock_requests_slow

@pytest.mark.asyncio
async def test_run_intermittent_engine_failure_reports_error(mock_all_runtime_components, fastapi_test_client):
    """
    Test that 'imrabo run' reports errors clearly when the underlying engine has intermittent failures.
    """
    async def flaky_execute_generator(request):
        yield ExecutionResult(request_id="flaky-req", status="streaming", output={"content": "Working..."}, metrics={})
        if random.random() < 0.8: # Simulate failure *sometimes*
            raise RuntimeError("Engine fault!")
        yield ExecutionResult(request_id="flaky-req", status="completed", output={"content": ""}, metrics={})
    
    mock_all_runtime_components["mock_fastapi_kernel"].execute.side_effect = flaky_execute_generator

    # Need to retry a few times to hit the random failure
    num_attempts = 5
    failure_detected = False
    for _ in range(num_attempts):
        run_result = run_cli_command(["run"], input="flaky_prompt\n/exit\n")
        if "Error during prompt execution: RuntimeError('Engine fault!')" in run_result.stdout:
            failure_detected = True
            break
        elif "Working..." in run_result.stdout:
            # If it passed, reset kernel mock so next run also has chance to fail
            mock_all_runtime_components["mock_fastapi_kernel"].execute.side_effect = flaky_execute_generator
    
    assert failure_detected, "Intermittent engine failure was not detected after multiple attempts."
    assert run_result.exit_code == 0 # CLI should still exit cleanly, reporting the error

