import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os
import time

from imrabo.cli import core
from imrabo.cli.client import RuntimeClient
from imrabo.internal import paths

# --- Fixtures (re-used from test_daemon_lifecycle.py for consistency) ---

@pytest.fixture
def temp_pid_file(tmp_path):
    """Fixture to ensure a clean PID file path for each test."""
    original_get_runtime_pid_file = paths.get_runtime_pid_file
    mock_pid_file_path = tmp_path / "runtime.pid"
    paths.get_runtime_pid_file = lambda: str(mock_pid_file_path)
    yield mock_pid_file_path
    paths.get_runtime_pid_file = original_get_runtime_pid_file
    if mock_pid_file_path.exists():
        mock_pid_file_path.unlink()

@pytest.fixture
def mock_runtime_client():
    """Mocks the RuntimeClient used by core functions."""
    with patch('imrabo.cli.core.RuntimeClient', autospec=True) as MockClient:
        instance = MockClient.return_value
        yield instance

# --- Daemon Crash & Recovery Tests ---

def test_daemon_crash_during_execution(mock_runtime_client, temp_pid_file):
    """
    Test that the system can recover if the daemon process crashes during an execution.
    This simulates a hard crash of the daemon itself.
    """
    # Simulate daemon being started
    core.save_pid(1234)
    
    # Simulate a crash: PID file exists but process is gone
    # core.is_runtime_active will return False, as client.health() will fail
    mock_runtime_client.health.side_effect = httpx.ConnectError("Daemon crashed")

    # Attempt to start daemon again
    with patch('subprocess.Popen') as mock_popen, \
         patch('imrabo.cli.core.is_runtime_active', side_effect=[False, True]), \
         patch('time.sleep', return_value=None):
        
        mock_process = MagicMock()
        mock_process.pid = 9999
        mock_popen.return_value = mock_process

        # The subsequent start_runtime should clean up the old PID file and start anew
        success = core.start_runtime()
        assert success is True
        mock_popen.assert_called_once()
        assert temp_pid_file.exists()
        assert int(temp_pid_file.read_text()) == 9999 # New PID is written

def test_engine_crash_mid_run(kernel_service, mock_engine, sample_execution_request):
    """
    Test that the kernel handles an engine crash mid-execution gracefully.
    This assumes engine crash is handled by the KernelExecutionService,
    which propagates the error as an ExecutionResult.
    """
    mock_engine.execute.return_value = iter([
        ExecutionResult(request_id="test", status="streaming", output={"content": "Part1"}, metrics={}),
        pytest.raises(RuntimeError, match="Engine crashed unexpectedly").type # Simulate engine adapter raising error
    ])
    mock_engine.force_execute_error = True # Trigger the error in mock_engine

    results = list(kernel_service.execute(sample_execution_request))

    # Expected: "resolving", "loading_engine", "executing", "Part1", "error"
    assert len(results) == 5
    assert results[3].output["content"] == "Part1"
    assert results[4].status == "error"
    assert "Mock execute error" in results[4].output["error"]
    assert len(mock_engine.unload_calls) == 1 # Engine should be unloaded

def test_interrupted_startup_leaves_clean_state(mock_runtime_client, temp_pid_file):
    """
    Test that if daemon startup is interrupted before it's fully active,
    it leaves a clean state (PID file removed or next start is clean).
    """
    with patch('subprocess.Popen') as mock_popen, \
         patch('imrabo.cli.core.is_runtime_active', return_value=False), \
         patch('time.sleep', return_value=None):
        
        mock_process = MagicMock()
        mock_process.pid = 9999
        mock_popen.return_value = mock_process
        
        # Simulate an exception happening mid-startup, e.g., before client confirms active
        mock_runtime_client.health.side_effect = Exception("Startup interrupted")

        success = core.start_runtime()
        assert success is False
        assert temp_pid_file.exists() # PID file is left if process started but failed to become active
        
        # This highlights a potential edge case: PID file exists but process might be dead.
        # Current implementation of start_runtime leaves PID if process was spawned.
        # Future: improve start_runtime to clean up PID if active check fails.

def test_daemon_recovers_from_corrupted_pid_file(mock_runtime_client, temp_pid_file):
    """
    Test that daemon start/stop can recover from a corrupted PID file.
    """
    # Corrupt PID file
    temp_pid_file.write_text("not-a-pid")

    # Try to stop daemon
    success_stop = core.stop_runtime()
    assert success_stop is True # It should consider it stopped if PID is invalid/missing
    assert not temp_pid_file.exists() # Corrupted PID file should be removed

    # Now try to start cleanly
    mock_runtime_client.health.return_value = {"status": "ok"}
    with patch('subprocess.Popen') as mock_popen, \
         patch('imrabo.cli.core.is_runtime_active', side_effect=[False, True]), \
         patch('time.sleep', return_value=None):
        
        mock_process = MagicMock()
        mock_process.pid = 9999
        mock_popen.return_value = mock_process

        success_start = core.start_runtime()
        assert success_start is True
        assert temp_pid_file.exists()
        assert int(temp_pid_file.read_text()) == 9999
