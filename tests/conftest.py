import pytest
from unittest.mock import patch, MagicMock
import os
import random
import signal
import shutil
from pathlib import Path

import httpx
import requests

# --- Failure Injection Fixtures ---

@pytest.fixture
def mock_random_os_kill():
    """
    A fixture to mock `os.kill` to randomly raise `ProcessLookupError`
    or `OSError` to simulate process termination/failure.
    """
    original_os_kill = os.kill
    def flaky_os_kill(pid, sig):
        if random.random() < 0.3: # 30% chance to fail
            if sig == signal.SIGTERM:
                raise ProcessLookupError(f"Simulated SIGTERM failure for pid {pid}")
            else:
                raise OSError(f"Simulated OSError during kill for pid {pid}")
        original_os_kill(pid, sig)
    
    with patch('os.kill', side_effect=flaky_os_kill) as mock_kill:
        yield mock_kill

@pytest.fixture
def mock_disk_full_error(mocker):
    """
    A fixture to simulate a 'disk full' error when writing to disk.
    Mocks `Path.write_text` and `shutil.disk_usage`.
    """
    original_path_write_text = Path.write_text
    def flaky_write_text(self, data, encoding=None, errors=None):
        if random.random() < 0.5: # 50% chance to fail
            raise OSError(28, "No space left on device")
        return original_path_write_text(self, data, encoding, errors)

    mocker.patch('pathlib.Path.write_text', side_effect=flaky_write_text)
    mocker.patch('shutil.disk_usage', return_value=(100, 100, 0)) # 0 bytes free
    yield


@pytest.fixture
def mock_network_interruption(mocker):
    """
    A fixture to simulate intermittent network interruptions for HTTP requests.
    Patches `requests.get`, `requests.post`, and `httpx` methods.
    """
    def flaky_request(*args, **kwargs):
        if random.random() < 0.4: # 40% chance to raise ConnectionError
            if 'httpx' in str(mocker.patch.target): # Check if patching httpx
                raise httpx.ConnectError("Simulated network interruption by httpx")
            else:
                raise requests.exceptions.ConnectionError("Simulated network interruption by requests")
        
        # If not failing, return a mocked response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_response.iter_lines.return_value = [b'data: {"content": "OK", "stop": true}'] # For streaming
        mock_response.__enter__.return_value = mock_response # For context manager
        return mock_response
    
    mocker.patch('requests.get', side_effect=flaky_request)
    mocker.patch('requests.post', side_effect=flaky_request)
    mocker.patch('httpx.AsyncClient.get', side_effect=flaky_request)
    mocker.patch('httpx.AsyncClient.post', side_effect=flaky_request)
    yield


@pytest.fixture
def mock_subprocess_execution_failure():
    """
    A fixture to simulate an external subprocess (e.g., llama-server) failing to execute.
    """
    with patch('subprocess.Popen', side_effect=subprocess.CalledProcessError(1, "mock_cmd")) as mock_popen:
        yield mock_popen

