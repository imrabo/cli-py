import pytest
import time
from unittest.mock import MagicMock
from imrabo.kernel.contracts import ExecutionRequest, ExecutionResult, ArtifactHandle
from imrabo.kernel.execution import KernelExecutionService
from tests.kernel.mocks import MockArtifactResolver, MockEngineAdapter
import sys
import psutil # For basic memory usage checks

# --- Fixtures (re-used from kernel tests for consistency) ---

@pytest.fixture
def mock_artifact_handle():
    return ArtifactHandle(ref="model:perf-test/variant:v1", is_available=True, location=Path("/tmp/perf-model.gguf"), metadata={})

@pytest.fixture
def mock_resolver(mock_artifact_handle):
    return MockArtifactResolver(default_handle=mock_artifact_handle)

@pytest.fixture
def mock_engine_perf():
    # Configure mock engine to yield a long stream of data
    results = []
    for i in range(100): # 100 parts of output
        results.append(ExecutionResult(request_id="perf-req", status="streaming", output={"content": f"part {i} "}, metrics={}))
    results.append(ExecutionResult(request_id="perf-req", status="completed", output={"content": ""}, metrics={"duration_sec": 0.123}))
    return MockEngineAdapter(results_to_yield=results)

@pytest.fixture
def kernel_service_perf(mock_resolver, mock_engine_perf):
    return KernelExecutionService(
        artifact_resolver=mock_resolver,
        engine_adapter=mock_engine_perf
    )

@pytest.fixture
def sample_execution_request_perf():
    return ExecutionRequest(
        request_id="perf-req-1",
        artifact_ref="model:perf-test/variant:v1",
        input={"prompt": "Generate a long text"},
        constraints={},
        capabilities=["stream"]
    )

# --- Performance & Resource Tests ---

def test_kernel_execution_time_for_mocked_run(kernel_service_perf, sample_execution_request_perf):
    """
    Test the execution time of a kernel run (with mocked adapters).
    This establishes a baseline for core logic overhead.
    """
    start_time = time.perf_counter()
    list(kernel_service_perf.execute(sample_execution_request_perf))
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    # Assert against a reasonable upper bound for mocked execution
    # This value needs tuning based on actual test environment.
    # For now, a very generous bound.
    assert duration < 0.1 # Should be very fast with mocks

def test_kernel_repeated_execution_no_significant_memory_growth(kernel_service_perf, sample_execution_request_perf):
    """
    Verify that repeated kernel executions (with mocked adapters) do not lead
    to significant memory leaks in the kernel's Python process.
    """
    process = psutil.Process(os.getpid())
    
    # Get initial memory usage
    initial_memory_mb = process.memory_info().rss / (1024 * 1024)
    
    num_runs = 100 # Perform multiple runs to amplify any leak
    for _ in range(num_runs):
        list(kernel_service_perf.execute(sample_execution_request_perf))
        # Ensure engine is unloaded to reset state for subsequent run
        kernel_service_perf.unload_engine()
    
    final_memory_mb = process.memory_info().rss / (1024 * 1024)
    memory_growth_mb = final_memory_mb - initial_memory_mb
    
    # Define an acceptable memory growth threshold (e.g., 5 MB for 100 runs)
    # This value is highly dependent on the system and code, needs calibration.
    assert memory_growth_mb < 5.0, f"Memory growth detected: {memory_growth_mb:.2f} MB"
    
def test_kernel_repeated_engine_load_unload_no_significant_memory_growth(mock_resolver):
    """
    Verify that repeated engine load/unload cycles do not lead to significant memory leaks.
    """
    process = psutil.Process(os.getpid())
    mock_engine = MockEngineAdapter() # A fresh engine for load/unload cycles

    initial_memory_mb = process.memory_info().rss / (1024 * 1024)
    
    num_cycles = 50
    for _ in range(num_cycles):
        kernel_service = KernelExecutionService(artifact_resolver=mock_resolver, engine_adapter=mock_engine)
        request = ExecutionRequest(
            request_id="load-unload-req",
            artifact_ref="model:perf-test/variant:v1",
            input={"prompt": "test"},
            constraints={},
            capabilities=["stream"]
        )
        list(kernel_service.execute(request)) # Loads engine
        kernel_service.unload_engine() # Unloads engine

    final_memory_mb = process.memory_info().rss / (1024 * 1024)
    memory_growth_mb = final_memory_mb - initial_memory_mb

    assert memory_growth_mb < 5.0, f"Memory growth detected: {memory_growth_mb:.2f} MB"
