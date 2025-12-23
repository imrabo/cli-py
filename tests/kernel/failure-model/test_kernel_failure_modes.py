import pytest
from unittest.mock import MagicMock
from pathlib import Path

from imrabo.kernel.contracts import ExecutionRequest, ExecutionResult, ArtifactHandle
from imrabo.kernel.execution import KernelExecutionService
from tests.kernel.mocks import MockArtifactResolver, MockEngineAdapter

# --- Fixtures (re-used from test_execution_lifecycle.py for consistency) ---
@pytest.fixture
def mock_artifact_handle():
    return ArtifactHandle(ref="model:test/variant:v1", is_available=True, location=Path("/tmp/model.gguf"), metadata={})

@pytest.fixture
def mock_resolver(mock_artifact_handle):
    return MockArtifactResolver(default_handle=mock_artifact_handle)

@pytest.fixture
def mock_engine():
    # Pre-configure engine to yield a simple result
    return MockEngineAdapter(results_to_yield=[
        ExecutionResult(request_id="test-req", status="streaming", output={"content": "Hello"}, metrics={}),
        ExecutionResult(request_id="test-req", status="completed", output={"content": "World"}, metrics={}),
    ])

@pytest.fixture
def kernel_service(mock_resolver, mock_engine):
    return KernelExecutionService(
        artifact_resolver=mock_resolver,
        engine_adapter=mock_engine
    )

@pytest.fixture
def sample_execution_request():
    return ExecutionRequest(
        request_id="test-req",
        artifact_ref="model:test/variant:v1",
        input={"prompt": "Say hello world"},
        constraints={},
        capabilities=["stream"]
    )

# --- Kernel Failure Model Tests ---

def test_kernel_handles_artifact_resolution_error(kernel_service, mock_resolver, sample_execution_request):
    """
    Test that kernel returns an error ExecutionResult when artifact resolution fails.
    """
    mock_resolver.force_ensure_available_error = True
    results = list(kernel_service.execute(sample_execution_request))

    assert len(results) == 2 # "resolving" message + "error" result
    assert results[0].status == "resolving"
    assert results[1].status == "error"
    assert "Mock ensure_available error" in results[1].output["error"]
    assert sample_execution_request.request_id == results[1].request_id


def test_kernel_handles_engine_load_error(kernel_service, mock_engine, sample_execution_request):
    """
    Test that kernel returns an error ExecutionResult when engine loading fails.
    """
    mock_engine.force_load_error = True
    results = list(kernel_service.execute(sample_execution_request))

    assert len(results) == 3 # "resolving" + "loading_engine" + "error"
    assert results[0].status == "resolving"
    assert results[1].status == "loading_engine"
    assert results[2].status == "error"
    assert "Mock load error" in results[2].output["error"]
    assert sample_execution_request.request_id == results[2].request_id
    assert len(mock_engine.unload_calls) == 1 # Unload should still be called


def test_kernel_handles_engine_execution_error(kernel_service, mock_engine, sample_execution_request):
    """
    Test that kernel returns an error ExecutionResult when engine execution fails.
    """
    mock_engine.force_execute_error = True
    results = list(kernel_service.execute(sample_execution_request))

    assert len(results) == 4 # "resolving" + "loading_engine" + "executing" + "error"
    assert results[0].status == "resolving"
    assert results[1].status == "loading_engine"
    assert results[2].status == "executing"
    assert results[3].status == "error"
    assert "Mock execute error" in results[3].output["error"]
    assert sample_execution_request.request_id == results[3].request_id
    assert len(mock_engine.unload_calls) == 1 # Unload should still be called


def test_kernel_handles_partial_execution_interruption(mock_resolver, sample_execution_request):
    """
    Test that kernel gracefully handles engine stopping mid-stream.
    """
    # Configure mock engine to yield some results, then raise error
    mock_engine_partial = MockEngineAdapter(results_to_yield=[
        ExecutionResult(request_id="test-req", status="streaming", output={"content": "Part1"}, metrics={}),
        ExecutionResult(request_id="test-req", status="streaming", output={"content": "Part2"}, metrics={}),
    ])
    mock_engine_partial.force_execute_error = True # Force error after yielding some results
    
    kernel_service_partial = KernelExecutionService(mock_resolver, mock_engine_partial)
    results = list(kernel_service_partial.execute(sample_execution_request))

    # Expect: resolving, loading, executing, Part1, Part2, error
    assert len(results) == 6
    assert results[0].status == "resolving"
    assert results[1].status == "loading_engine"
    assert results[2].status == "executing"
    assert results[3].status == "streaming"
    assert results[3].output["content"] == "Part1"
    assert results[4].status == "streaming"
    assert results[4].output["content"] == "Part2"
    assert results[5].status == "error"
    assert "Mock execute error" in results[5].output["error"]
    assert sample_execution_request.request_id == results[5].request_id
    assert len(mock_engine_partial.unload_calls) == 1 # Unload should still be called


def test_kernel_ensures_engine_unload_on_any_execution_error(kernel_service, mock_engine, sample_execution_request):
    """
    Verify that the engine is always unloaded when an execution fails,
    regardless of where the error occurred.
    """
    # Test with artifact resolution error
    mock_engine.unload_calls = [] # Reset calls
    kernel_service.artifact_resolver.force_ensure_available_error = True
    list(kernel_service.execute(sample_execution_request))
    assert len(mock_engine.unload_calls) == 0 # Engine was never loaded

    # Test with engine load error
    kernel_service.artifact_resolver.force_ensure_available_error = False
    mock_engine.unload_calls = [] # Reset calls
    mock_engine.force_load_error = True
    list(kernel_service.execute(sample_execution_request))
    assert len(mock_engine.unload_calls) == 1 # Engine was attempted to be loaded, then unloaded

    # Test with engine execute error
    mock_engine.force_load_error = False
    mock_engine.unload_calls = [] # Reset calls
    mock_engine.force_execute_error = True
    list(kernel_service.execute(sample_execution_request))
    assert len(mock_engine.unload_calls) == 1 # Engine was loaded, then unloaded

