import httpx
import json
from typing import AsyncGenerator
from pathlib import Path

from imrabo.internal import paths
from imrabo.internal.constants import RUNTIME_HOST, RUNTIME_PORT
from imrabo.runtime.security import load_token, generate_token, save_token # Need save_token if it's not generated yet
from imrabo.internal.logging import get_logger

logger = get_logger()

class RuntimeClient:
    def __init__(self, host: str = RUNTIME_HOST, port: int = RUNTIME_PORT):
        self.base_url = f"http://{host}:{port}"
        self._token: str | None = None
        self._load_or_generate_token()

    def _load_or_generate_token(self):
        token_file = Path(paths.get_runtime_token_file())
        self._token = load_token(token_file)
        if not self._token:
            self._token = generate_token()
            save_token(self._token, token_file)
            logger.info("Generated new runtime token.")
        else:
            logger.info("Loaded existing runtime token.")

    def _get_headers(self):
        return {"Authorization": f"Bearer {self._token}"}

    async def _request(self, method: str, endpoint: str, **kwargs):
        try:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.request(method, endpoint.lstrip('/'), headers=self._get_headers(), **kwargs)
                response.raise_for_status()
                return response
        except httpx.RequestError as exc:
            logger.error(f"HTTP request failed to {self.base_url}/{endpoint}: {exc}")
            raise RuntimeError(f"Could not connect to runtime: {exc}")
        except httpx.HTTPStatusError as exc:
            logger.error(f"HTTP status error for {self.base_url}/{endpoint}: {exc.response.status_code} - {exc.response.text}")
            raise RuntimeError(f"Runtime error: {exc.response.status_code} - {exc.response.text}")

    async def health(self) -> dict:
        response = await self._request("GET", "/health")
        return response.json()

    async def status(self) -> dict:
        response = await self._request("GET", "/status")
        return response.json()

    async def shutdown(self) -> dict:
        response = await self._request("POST", "/shutdown")
        return response.json()

    async def run_prompt(self, prompt: str) -> AsyncGenerator[str, None]:
        url = f"{self.base_url.rstrip('/')}/run"
        headers = self._get_headers()
        json_payload = {"prompt": prompt}

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, headers=headers, json=json_payload, timeout=None) as response:
                    # Manually check for HTTP errors before trying to stream
                    if response.status_code >= 400:
                        # Consume the error response body before raising
                        error_body = await response.aread()
                        raise RuntimeError(f"Runtime returned an error: {response.status_code} - {error_body.decode()}")

                    # Stream the response content
                    async for chunk in response.aiter_bytes():
                        lines = chunk.decode('utf-8').split('\n')
                        for line in lines:
                            if line.strip().startswith("data: "):
                                try:
                                    json_data = json.loads(line[len("data: "):])
                                    if "content" in json_data:
                                        yield json_data["content"]
                                    if json_data.get("stop"):
                                        return
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to decode JSON from SSE: {line}")
                                    continue
        except httpx.RequestError as exc:
            logger.error(f"Streaming request failed to {url}: {exc}")
            raise RuntimeError(f"Could not connect to runtime for prompt: {exc}")
        # The RuntimeError is now raised from within the try block


if __name__ == "__main__":
    async def test_client():
        client = RuntimeClient()
        print(f"Base URL: {client.base_url}")

        print("\n--- Testing Health Endpoint ---")
        try:
            health_response = await client.health()
            print(f"Health: {health_response}")
        except Exception as e:
            print(f"Health check failed: {e}")

        print("\n--- Testing Status Endpoint ---")
        try:
            status_response = await client.status()
            print(f"Status: {status_response}")
        except Exception as e:
            print(f"Status check failed: {e}")

        print("\n--- Testing Run Prompt Endpoint (simulated) ---")
        try:
            print("Prompting: 'Tell me a short story.'")
            async for chunk in client.run_prompt("Tell me a short story."):
                print(chunk, end="")
            print("\n")
        except Exception as e:
            print(f"Run prompt failed: {e}")

        # Note: Shutdown test will actually shut down the server if it's running
        # print("\n--- Testing Shutdown Endpoint ---")
        # try:
        #     shutdown_response = await client.shutdown()
        #     print(f"Shutdown: {shutdown_response}")
        # except Exception as e:
        #     print(f"Shutdown failed: {e}")

    # To run the test, you need to have a runtime server running in the background.
    # asyncio.run(test_client())
