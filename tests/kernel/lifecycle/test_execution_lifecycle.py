import pytest
from unittest.mock import MagicMock
from imrabo.kernel.contracts import ExecutionRequest, ExecutionResult, ArtifactHandle
from imrabo.kernel.execution import KernelExecutionService
from tests.kernel.mocks import MockArtifactResolver, MockEngineAdapter

# --- Fixtures ---
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

# --- Valid Lifecycle Progression ---
def test_valid_lifecycle_progression(kernel_service, mock_resolver, mock_engine, sample_execution_request):
    """
    Tests a complete, successful execution from artifact resolution to engine execution
    and result streaming.
    """
    results = list(kernel_service.execute(sample_execution_request))

    # Expected results structure:
    # 1. Resolving message
    # 2. Loading engine message
    # 3. Executing message
    # 4. Engine streaming result 1
    # 5. Engine streaming result 2
    # 6. Completed message

    assert len(results) == 6
    assert results[0].status == "resolving"
    assert "Resolving artifact" in results[0].output["message"]
    assert results[1].status == "loading_engine"
    assert "Loading engine" in results[1].output["message"]
    assert results[2].status == "executing"
    assert "Executing request" in results[2].output["message"]
    assert results[3].status == "streaming"
    assert results[3].output["content"] == "Hello"
    assert results[4].status == "completed" # This comes from engine, should be 'streaming' then 'completed'
    assert results[4].output["content"] == "World"
    assert results[5].status == "completed"
    assert "Execution finished" in results[5].output["message"]

    assert sample_execution_request.artifact_ref in mock_resolver.ensure_available_calls
    assert len(mock_engine.load_calls) == 1
    assert len(mock_engine.execute_calls) == 1
    assert mock_engine.loaded_artifact_ref == sample_execution_request.artifact_ref
    assert not mock_engine.unload_calls # Engine should stay loaded after successful run


def test_engine_stays_loaded_for_same_artifact(kernel_service, mock_resolver, mock_engine, sample_execution_request):
    """
    Verify engine is not reloaded if the same artifact is requested again.
    """
    # First execution
    list(kernel_service.execute(sample_execution_request))
    assert len(mock_engine.load_calls) == 1
    assert len(mock_engine.unload_calls) == 0

    # Second execution with same request
    list(kernel_service.execute(sample_execution_request))
    assert len(mock_engine.load_calls) == 1 # Load should not be called again
    assert len(mock_engine.unload_calls) == 0 # Unload should not be called

def test_engine_reloads_for_different_artifact(mock_artifact_handle, mock_resolver, mock_engine):
    """
    Verify engine reloads if a different artifact is requested.
    """
    service = KernelExecutionService(mock_resolver, mock_engine)
    req1 = ExecutionRequest(request_id="req1", artifact_ref="model:test/variant:v1", input={}, constraints={}, capabilities=[])
    req2 = ExecutionRequest(request_id="req2", artifact_ref="model:test2/variant:v1", input={}, constraints={}, capabilities=[])

    # First execution
    list(service.execute(req1))
    assert len(mock_engine.load_calls) == 1
    assert len(mock_engine.unload_calls) == 0

    # Simulate new artifact handle for resolver (different model)
    mock_resolver._default_handle = ArtifactHandle(ref="model:test2/variant:v1", is_available=True, location=Path("/tmp/model2.gguf"), metadata={})

    # Second execution with different request
    list(service.execute(req2))
    assert len(mock_engine.load_calls) == 2 # Load should be called again
    assert len(mock_engine.unload_calls) == 1 # Unload should have been called before reloading

# --- Failure Scenarios ---
def test_lifecycle_failure_during_artifact_resolution(kernel_service, mock_resolver, mock_engine, sample_execution_request):
    """
    Test that execution fails gracefully if artifact resolution fails.
    """
    mock_resolver.force_ensure_available_error = True
    results = list(kernel_service.execute(sample_execution_request))

    assert len(results) == 2 # Resolving message + Error result
    assert results[0].status == "resolving"
    assert results[1].status == "error"
    assert "Mock ensure_available error" in results[1].output["error"]
    assert len(mock_engine.load_calls) == 0 # Engine should not be loaded
    assert len(mock_engine.execute_calls) == 0
    assert len(mock_engine.unload_calls) == 0 # Engine never loaded, so no unload

def test_lifecycle_failure_if_artifact_not_available(kernel_service, mock_resolver, mock_engine, sample_execution_request):
    """
    Test that execution fails if artifact is resolved but not available.
    """
    mock_resolver._default_handle = ArtifactHandle(ref="model:test/variant:v1", is_available=False, location=None, metadata={})
    results = list(kernel_service.execute(sample_execution_request))

    assert len(results) == 2
    assert results[0].status == "resolving"
    assert results[1].status == "error"
    assert "Artifact not available" in results[1].output["error"]
    assert len(mock_engine.load_calls) == 0
    assert len(mock_engine.execute_calls) == 0

def test_lifecycle_failure_during_engine_loading(kernel_service, mock_resolver, mock_engine, sample_execution_request):
    """
    Test that execution fails gracefully if engine loading fails.
    """
    mock_engine.force_load_error = True
    results = list(kernel_service.execute(sample_execution_request))

    assert len(results) == 3 # Resolving + Loading message + Error result
    assert results[0].status == "resolving"
    assert results[1].status == "loading_engine"
    assert results[2].status == "error"
    assert "Mock load error" in results[2].output["error"]
    assert len(mock_engine.execute_calls) == 0
    assert len(mock_engine.unload_calls) == 1 # Unload should be called even after failed load to clean up

def test_lifecycle_failure_during_engine_execution(kernel_service, mock_resolver, mock_engine, sample_execution_request):
    """
    Test that execution fails gracefully if engine execution fails.
    """
    mock_engine.force_execute_error = True
    results = list(kernel_service.execute(sample_execution_request))

    assert len(results) == 4 # Resolving + Loading + Executing message + Error result
    assert results[0].status == "resolving"
    assert results[1].status == "loading_engine"
    assert results[2].status == "executing"
    assert results[3].status == "error"
    assert "Mock execute error" in results[3].output["error"]
    assert len(mock_engine.unload_calls) == 1 # Unload should be called

def test_explicit_engine_unload(kernel_service, mock_engine, sample_execution_request):
    """
    Test that explicit unload of the engine works.
    """
    list(kernel_service.execute(sample_execution_request)) # Load the engine
    assert mock_engine.loaded_artifact_ref is not None
    assert len(mock_engine.load_calls) == 1
    assert len(mock_engine.unload_calls) == 0

    kernel_service.unload_engine()
    assert mock_engine.loaded_artifact_ref is None
    assert len(mock_engine.unload_calls) == 1

def test_explicit_engine_unload_when_not_loaded(kernel_service, mock_engine):
    """
    Test that explicit unload of engine when nothing is loaded is a no-op.
    """
    kernel_service.unload_engine()
    assert len(mock_engine.unload_calls) == 0

def test_engine_unloads_on_error_during_second_run(mock_artifact_handle, mock_resolver, mock_engine):
    """
    Test that if an error occurs during a subsequent run, the engine is unloaded.
    """
    service = KernelExecutionService(mock_resolver, mock_engine)
    req1 = ExecutionRequest(request_id="req1", artifact_ref="model:test/variant:v1", input={}, constraints={}, capabilities=[])

    # First successful execution
    list(service.execute(req1))
    assert service._is_engine_loaded
    assert len(mock_engine.unload_calls) == 0

    # Second execution, but force an execute error
    mock_engine.force_execute_error = True
    results_second_run = list(service.execute(req1))

    assert results_second_run[-1].status == "error"
    assert not service._is_engine_loaded
    assert len(mock_engine.unload_calls) == 1 # Engine should have been unloaded

