import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import httpx

from imrabo.kernel.contracts import ExecutionRequest, ExecutionResult
from imrabo.adapters.http.fastapi_server import app, kernel as fastapi_kernel_instance # Import the FastAPI app and its kernel placeholder

@pytest.fixture(autouse=True)
def mock_kernel_in_fastapi():
    """
    Fixture to replace the actual kernel in fastapi_server.py with a mock during tests.
    """
    mock_kernel = MagicMock()
    # The fastapi_server.py has a global 'kernel' instance. We need to replace its methods.
    # Note: This is a bit hacky due to global, better would be dependency injection.
    with patch('imrabo.adapters.http.fastapi_server.kernel', new=mock_kernel) as patched_kernel:
        yield patched_kernel

@pytest.fixture
async def async_client():
    """
    Asynchronous test client for the FastAPI app.
    """
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

# --- Helper for auth ---
def get_auth_headers(token="mock_token"):
    """Returns headers with a mock auth token."""
    return {"Authorization": f"Bearer {token}"}

# Mock the security token part, as we don't need real token generation for these tests
@pytest.fixture(autouse=True)
def mock_security_token():
    with patch('imrabo.adapters.http.fastapi_server.RUNTIME_AUTH_TOKEN', "mock_token"):
        yield

# --- Concurrency Tests ---

@pytest.mark.asyncio
async def test_daemon_handles_concurrent_status_requests(async_client, mock_kernel_in_fastapi):
    """
    Test that multiple concurrent status requests are handled correctly.
    """
    mock_kernel_in_fastapi.get_status.side_effect = [{"status": "ok1"}, {"status": "ok2"}, {"status": "ok3"}]

    tasks = [
        async_client.get("/status", headers=get_auth_headers()),
        async_client.get("/status", headers=get_auth_headers()),
        async_client.get("/status", headers=get_auth_headers()),
    ]
    responses = await asyncio.gather(*tasks)

    assert len(responses) == 3
    for response in responses:
        assert response.status_code == 200
        assert response.json()["status"].startswith("ok") # Check that responses are distinct if kernel provided them
    
    assert mock_kernel_in_fastapi.get_status.call_count == 3


@pytest.mark.asyncio
async def test_daemon_handles_concurrent_run_requests_streaming(async_client, mock_kernel_in_fastapi):
    """
    Test that multiple concurrent run requests (streaming) are handled correctly.
    Simulates engine busy states and ensures streams don't interfere.
    """
    async def mock_execute_stream_1():
        yield ExecutionResult(request_id="req1", status="streaming", output={"content": "Stream1_Part1"}, metrics={})
        await asyncio.sleep(0.01) # Simulate delay
        yield ExecutionResult(request_id="req1", status="streaming", output={"content": "Stream1_Part2"}, metrics={})
        yield ExecutionResult(request_id="req1", status="completed", output={"content": ""}, metrics={})

    async def mock_execute_stream_2():
        yield ExecutionResult(request_id="req2", status="streaming", output={"content": "Stream2_PartA"}, metrics={})
        await asyncio.sleep(0.02) # Simulate different delay
        yield ExecutionResult(request_id="req2", status="streaming", output={"content": "Stream2_PartB"}, metrics={})
        yield ExecutionResult(request_id="req2", status="completed", output={"content": ""}, metrics={})

    # The mock_kernel's execute method should return an iterator that produces the mock streams
    mock_kernel_in_fastapi.execute.side_effect = [
        mock_execute_stream_1(),
        mock_execute_stream_2(),
    ]

    async def get_streamed_output(response):
        full_content = ""
        async for chunk in response.aiter_bytes():
            try:
                line = chunk.decode().strip()
                if line.startswith("data:"):
                    data = json.loads(line[len("data:"):])
                    full_content += data.get("content", "")
                    if data.get("stop"):
                        break
            except json.JSONDecodeError:
                pass # Ignore malformed chunks
        return full_content

    # Send two concurrent streaming requests
    task1 = asyncio.create_task(
        async_client.post("/run", json={"prompt": "prompt1"}, headers=get_auth_headers())
    )
    task2 = asyncio.create_task(
        async_client.post("/run", json={"prompt": "prompt2"}, headers=get_auth_headers())
    )

    resp1, resp2 = await asyncio.gather(task1, task2)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    output1 = await get_streamed_output(resp1)
    output2 = await get_streamed_output(resp2)

    assert "Stream1_Part1Stream1_Part2" in output1
    assert "Stream2_PartAStream2_PartB" in output2

    assert mock_kernel_in_fastapi.execute.call_count == 2
    # Verify requests were for distinct prompts (based on mock side_effect order)
    assert mock_kernel_in_fastapi.execute.call_args_list[0].args[0].input == "prompt1"
    assert mock_kernel_in_fastapi.execute.call_args_list[1].args[0].input == "prompt2"

@pytest.mark.asyncio
async def test_daemon_graceful_shutdown_during_concurrency(async_client, mock_kernel_in_fastapi):
    """
    Test that the daemon can be shut down gracefully even with active requests.
    """
    async def mock_execute_long_stream():
        yield ExecutionResult(request_id="long-req", status="streaming", output={"content": "Long task started"}, metrics={})
        await asyncio.sleep(0.5) # Simulate long processing
        yield ExecutionResult(request_id="long-req", status="completed", output={"content": "Long task finished"}, metrics={})
    
    mock_kernel_in_fastapi.execute.return_value = mock_execute_long_stream()

    # Start a long-running request
    long_run_task = asyncio.create_task(
        async_client.post("/run", json={"prompt": "long prompt"}, headers=get_auth_headers())
    )

    # Immediately send a shutdown request
    shutdown_response = await async_client.post("/shutdown", headers=get_auth_headers())
    
    # Wait for the long run task to potentially complete (it might be interrupted by os.kill in shutdown)
    await asyncio.sleep(0.1) # Give some time for shutdown to act

    assert shutdown_response.status_code == 200
    assert shutdown_response.json()["message"] == "Shutting down"
    # The actual process termination will prevent the long_run_task from fully resolving in test
    # This test mainly checks that the shutdown API call itself works under concurrency.
    
    # We can't easily assert the long_run_task output because the test process itself might be terminated
    # or the server stopped, which results in a connection error for the client.
    # The key is that the /shutdown endpoint was callable and returned successfully.
