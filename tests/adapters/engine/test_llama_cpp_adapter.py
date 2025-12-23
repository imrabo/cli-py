import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import subprocess
import os
import requests

from imrabo.adapters.llama_cpp.process import LlamaCppProcessAdapter
from imrabo.kernel.contracts import ArtifactHandle, ExecutionRequest, ExecutionResult
from imrabo.internal import paths

# --- Fixtures ---

@pytest.fixture
def mock_llama_server_binary_path(tmp_path):
    """Mocks the path to the llama-server.exe binary."""
    binary_path = tmp_path / "llama-server.exe"
    binary_path.touch() # Create a dummy binary file
    with patch('imrabo.internal.paths.get_llama_server_binary_path', return_value=str(binary_path)):
        yield binary_path

@pytest.fixture
def mock_model_path(tmp_path):
    """Mocks a valid model path."""
    model_path = tmp_path / "model.gguf"
    model_path.touch() # Create a dummy model file
    yield model_path

@pytest.fixture
def mock_artifact_handle(mock_model_path):
    """Provides a valid ArtifactHandle for testing."""
    return ArtifactHandle(ref="model:test", is_available=True, location=mock_model_path, metadata={})

@pytest.fixture
def llama_adapter(mock_llama_server_binary_path):
    """Provides an instance of the LlamaCppProcessAdapter."""
    adapter = LlamaCppProcessAdapter()
    yield adapter
    # Ensure cleanup after test
    adapter.unload()

@pytest.fixture
def mock_subprocess_popen():
    """Mocks subprocess.Popen for controlling the external process."""
    with patch('subprocess.Popen') as mock_popen:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None # Process is running
        mock_popen.return_value = mock_process
        yield mock_popen

@pytest.fixture
def mock_requests_get():
    """Mocks requests.get for health checks."""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        yield mock_get

@pytest.fixture
def mock_requests_post():
    """Mocks requests.post for inference."""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        
        # Mock for streaming response
        mock_response.iter_lines.return_value = [
            b'data: {"content": "Hello", "stop": false}',
            b'data: {"content": " world", "stop": false}',
            b'data: {"content": "", "stop": true}'
        ]
        mock_post.return_value.__enter__.return_value = mock_response
        yield mock_post

# --- Tests ---

def test_load_engine_success(llama_adapter, mock_artifact_handle, mock_subprocess_popen, mock_requests_get, mock_model_path):
    """Test successful engine loading."""
    llama_adapter.load(mock_artifact_handle)
    mock_subprocess_popen.assert_called_once()
    assert llama_adapter.pid == 12345
    assert llama_adapter.server_ready is True
    mock_requests_get.assert_called_with(LlamaCppProcessAdapter.HEALTH_ENDPOINT, timeout=pytest.approx(1))
    
    # Check that model_path is correctly set in adapter
    assert llama_adapter.model_path == mock_model_path

def test_load_engine_binary_not_found(llama_adapter, mock_artifact_handle, tmp_path):
    """Test engine loading fails if llama-server.exe is not found."""
    non_existent_binary = tmp_path / "non_existent.exe"
    with patch('imrabo.internal.paths.get_llama_server_binary_path', return_value=str(non_existent_binary)):
        with pytest.raises(FileNotFoundError, match="llama-server.exe not found"):
            llama_adapter.load(mock_artifact_handle)

def test_load_engine_model_path_not_found(llama_adapter, mock_artifact_handle, mock_llama_server_binary_path, tmp_path):
    """Test engine loading fails if model file is not found."""
    non_existent_model = tmp_path / "non_existent.gguf"
    mock_artifact_handle.location = non_existent_model # Update handle location
    with pytest.raises(FileNotFoundError, match="Model file not found"):
        llama_adapter.load(mock_artifact_handle)

def test_load_engine_subprocess_error(llama_adapter, mock_artifact_handle, mock_llama_server_binary_path, mock_subprocess_popen):
    """Test engine loading fails if subprocess.Popen raises an error."""
    mock_subprocess_popen.side_effect = subprocess.CalledProcessError(1, "cmd")
    with pytest.raises(RuntimeError, match="Failed to start llama-server"):
        llama_adapter.load(mock_artifact_handle)

def test_load_engine_timeout_on_readiness(llama_adapter, mock_artifact_handle, mock_subprocess_popen, mock_requests_get):
    """Test engine loading times out if server doesn't become ready."""
    # Simulate health check never returning "ok"
    mock_requests_get.side_effect = requests.exceptions.ConnectionError("Server not up")
    with pytest.raises(RuntimeError, match="llama-server failed to become ready"):
        llama_adapter.load(mock_artifact_handle)

def test_unload_engine_success(llama_adapter, mock_artifact_handle, mock_subprocess_popen, mock_requests_get):
    """Test successful engine unloading."""
    llama_adapter.load(mock_artifact_handle)
    llama_adapter.unload()
    mock_subprocess_popen.return_value.terminate.assert_called_once()
    mock_subprocess_popen.return_value.wait.assert_called_once()
    assert llama_adapter.process is None
    assert llama_adapter.pid is None
    assert llama_adapter.server_ready is False

def test_unload_engine_when_not_loaded(llama_adapter):
    """Test unloading when no engine is loaded is a no-op."""
    llama_adapter.unload()
    # Assert no errors and no calls to subprocess methods
    assert llama_adapter.process is None

def test_unload_engine_force_kill(llama_adapter, mock_artifact_handle, mock_subprocess_popen, mock_requests_get):
    """Test engine is force-killed if graceful termination fails."""
    llama_adapter.load(mock_artifact_handle)
    mock_subprocess_popen.return_value.wait.side_effect = TimeoutError # Simulate graceful wait timeout
    llama_adapter.unload()
    mock_subprocess_popen.return_value.terminate.assert_called_once()
    mock_subprocess_popen.return_value.wait.assert_called_once()
    mock_subprocess_popen.return_value.kill.assert_called_once() # Force kill should be called

def test_execute_success(llama_adapter, mock_artifact_handle, mock_subprocess_popen, mock_requests_get, mock_requests_post):
    """Test successful inference execution."""
    llama_adapter.load(mock_artifact_handle)
    request = ExecutionRequest(
        request_id="exec-1",
        artifact_ref="model:test",
        input="What is 1+1?",
        constraints={},
        capabilities=[]
    )
    results = list(llama_adapter.execute(request))

    assert len(results) == 3
    assert results[0].status == "streaming"
    assert results[0].output["content"] == "Hello"
    assert results[1].status == "streaming"
    assert results[1].output["content"] == " world"
    assert results[2].status == "completed"
    assert results[2].output["content"] == ""

    mock_requests_post.assert_called_once_with(
        LlamaCppProcessAdapter.INFER_ENDPOINT,
        json=pytest.approx({"prompt": "What is 1+1?", "n_predict": 512, "temperature": 0.7, "stream": True}),
        stream=True,
        timeout=pytest.approx(60)
    )

def test_execute_engine_not_ready(llama_adapter):
    """Test execute fails if engine is not ready."""
    request = ExecutionRequest(request_id="exec-1", artifact_ref="model:test", input="?", constraints={}, capabilities=[])
    with pytest.raises(RuntimeError, match="llama-server is not ready"):
        list(llama_adapter.execute(request))

def test_execute_streaming_interruption(llama_adapter, mock_artifact_handle, mock_subprocess_popen, mock_requests_get, mock_requests_post):
    """Test execute handles network interruption during streaming."""
    llama_adapter.load(mock_artifact_handle)
    
    # Simulate network error during streaming
    mock_requests_post.return_value.__enter__.return_value.iter_lines.side_effect = requests.exceptions.ConnectionError("Network dropped")

    request = ExecutionRequest(request_id="exec-1", artifact_ref="model:test", input="?", constraints={}, capabilities=[])
    results = list(llama_adapter.execute(request))

    assert len(results) == 1 # Only the error result
    assert results[0].status == "error"
    assert "ConnectionError('Network dropped')" in results[0].output["error"]


def test_execute_malformed_output(llama_adapter, mock_artifact_handle, mock_subprocess_popen, mock_requests_get, mock_requests_post):
    """Test execute handles malformed JSON output from engine."""
    llama_adapter.load(mock_artifact_handle)
    
    # Simulate engine returning malformed JSON
    mock_requests_post.return_value.__enter__.return_value.iter_lines.return_value = [
        b'data: {"content": "Hello", "stop": false}',
        b'data: NOT JSON', # Malformed line
        b'data: {"content": "", "stop": true}'
    ]
    
    request = ExecutionRequest(request_id="exec-1", artifact_ref="model:test", input="?", constraints={}, capabilities=[])
    results = list(llama_adapter.execute(request))

    # Should still yield valid parts and handle malformed gracefully (logging, not crashing)
    assert len(results) == 3 # Hello, empty, completed
    assert results[0].output["content"] == "Hello"
    assert results[1].output["content"] == "" # Malformed line is ignored, then next valid data is processed
    assert results[2].status == "completed"

def test_execute_timeout(llama_adapter, mock_artifact_handle, mock_subprocess_popen, mock_requests_get, mock_requests_post):
    """Test execute handles timeout during inference."""
    llama_adapter.load(mock_artifact_handle)
    
    # Simulate a timeout
    mock_requests_post.side_effect = requests.exceptions.Timeout("Inference timeout")
    
    request = ExecutionRequest(request_id="exec-1", artifact_ref="model:test", input="?", constraints={}, capabilities=[])
    results = list(llama_adapter.execute(request))

    assert len(results) == 1
    assert results[0].status == "error"
    assert "Timeout('Inference timeout')" in results[0].output["error"]

