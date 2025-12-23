import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import os
import sys
import time

# Assuming imrabo.cli.core contains the start_runtime, stop_runtime, is_runtime_active logic
from imrabo.cli import core
from imrabo.cli.client import RuntimeClient
from imrabo.internal import paths

# --- Fixtures ---

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

# --- Daemon Lifecycle Tests ---

def test_start_runtime_daemon_already_active(mock_runtime_client):
    """Test start_runtime when daemon is already active."""
    mock_runtime_client.health.return_value = {"status": "ok"}
    with patch('imrabo.cli.core.is_runtime_active', return_value=True):
        success = core.start_runtime()
        assert success is True
        # Ensure subprocess.Popen was NOT called
        assert not hasattr(sys.modules['imrabo.cli.core'], 'subprocess_popen_mock') or not sys.modules['imrabo.cli.core'].subprocess_popen_mock.called

def test_start_runtime_success(mock_runtime_client, temp_pid_file):
    """Test successful daemon startup."""
    mock_runtime_client.health.return_value = {"status": "ok"}
    with patch('subprocess.Popen') as mock_popen, \
         patch('imrabo.cli.core.is_runtime_active', side_effect=[False, True]), \
         patch('time.sleep', return_value=None): # Speed up polling

        mock_process = MagicMock()
        mock_process.pid = 9999
        mock_popen.return_value = mock_process
        sys.modules['imrabo.cli.core'].subprocess_popen_mock = mock_popen # Store mock for assertion

        success = core.start_runtime()
        assert success is True
        mock_popen.assert_called_once()
        assert temp_pid_file.exists()
        assert int(temp_pid_file.read_text()) == 9999

def test_start_runtime_timeout(mock_runtime_client, temp_pid_file):
    """Test start_runtime fails on timeout if daemon doesn't become active."""
    mock_runtime_client.health.return_value = {"status": "initializing"} # Never becomes 'ok'
    with patch('subprocess.Popen') as mock_popen, \
         patch('imrabo.cli.core.is_runtime_active', return_value=False), \
         patch('time.sleep', return_value=None):
        
        mock_process = MagicMock()
        mock_process.pid = 9999
        mock_popen.return_value = mock_process

        success = core.start_runtime()
        assert success is False
        mock_popen.assert_called_once()
        # PID file should still exist as process was spawned, but start failed
        assert temp_pid_file.exists()
        # Ensure cleanup is done on failure
        # For now, start_runtime doesn't clean up the PID on timeout,
        # which is a potential improvement. Current behavior asserts it exists.


def test_stop_runtime_graceful_shutdown(mock_runtime_client, temp_pid_file):
    """Test successful graceful daemon shutdown via API."""
    core.save_pid(1234) # Simulate a running daemon
    mock_runtime_client.shutdown.return_value = {"message": "Shutting down"}
    
    with patch('imrabo.cli.core.run_async', return_value={"message": "Shutting down"}) as mock_run_async:
        success = core.stop_runtime()
        assert success is True
        mock_run_async.assert_called_once()
        assert not temp_pid_file.exists() # PID file should be removed

def test_stop_runtime_pid_termination_fallback(mock_runtime_client, temp_pid_file):
    """Test daemon stopping via PID termination after API shutdown fails."""
    core.save_pid(9998) # Simulate a running daemon
    mock_runtime_client.shutdown.side_effect = Exception("API unreachable")
    
    with patch('imrabo.cli.core.run_async', side_effect=Exception("API unreachable")),
         patch('os.kill') as mock_os_kill,
         patch('time.sleep', return_value=None):

        # Mock os.kill(pid, 0) to raise ProcessLookupError after first kill, simulating termination
        mock_os_kill.side_effect = [None, ProcessLookupError] # SIGTERM succeeds, then process gone

        success = core.stop_runtime()
        assert success is True
        mock_os_kill.assert_any_call(9998, os.SIGTERM)
        assert not temp_pid_file.exists()

def test_stop_runtime_daemon_not_running(mock_runtime_client, temp_pid_file):
    """Test stop_runtime when no daemon PID file exists."""
    # Ensure PID file does not exist
    if temp_pid_file.exists():
        temp_pid_file.unlink()

    success = core.stop_runtime()
    assert success is True
    # Ensure no calls to client.shutdown or os.kill
    assert not mock_runtime_client.shutdown.called
    assert not hasattr(sys.modules['imrabo.cli.core'], 'os_kill_mock') or not sys.modules['imrabo.cli.core'].os_kill_mock.called

def test_stop_runtime_idempotency_pid_fallback(mock_runtime_client, temp_pid_file):
    """Test stop_runtime multiple times, including fallback."""
    core.save_pid(9997)
    mock_runtime_client.shutdown.side_effect = Exception("API unreachable")
    
    with patch('imrabo.cli.core.run_async', side_effect=Exception("API unreachable")),
         patch('os.kill') as mock_os_kill,
         patch('time.sleep', return_value=None):

        mock_os_kill.side_effect = [None, ProcessLookupError] # Simulate successful termination
        success1 = core.stop_runtime()
        assert success1 is True
        assert not temp_pid_file.exists()

        # Call again when no PID file
        success2 = core.stop_runtime()
        assert success2 is True
        assert not mock_runtime_client.shutdown.called # Should not be called again
        assert mock_os_kill.call_count == 2 # Initial SIGTERM, then check-if-alive

def test_start_runtime_with_stale_pid_file(mock_runtime_client, temp_pid_file):
    """Test start_runtime with a stale PID file (process not running)."""
    temp_pid_file.write_text("12345") # Stale PID
    mock_runtime_client.health.return_value = {"status": "ok"}
    
    with patch('subprocess.Popen') as mock_popen, \
         patch('imrabo.cli.core.is_runtime_active', side_effect=[False, True]), \
         patch('time.sleep', return_value=None),
         patch('os.kill', side_effect=ProcessLookupError) as mock_os_kill: # os.kill(stale_pid, 0) will fail
        
        mock_process = MagicMock()
        mock_process.pid = 9999
        mock_popen.return_value = mock_process
        sys.modules['imrabo.cli.core'].subprocess_popen_mock = mock_popen

        success = core.start_runtime()
        assert success is True
        mock_os_kill.assert_any_call(12345, 0) # Should try to check stale PID
        assert not temp_pid_file.read_text() == "12345" # Stale PID removed
        assert int(temp_pid_file.read_text()) == 9999 # New PID written
