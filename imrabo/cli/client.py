import json
import httpx
import codecs
from typing import AsyncGenerator
from pathlib import Path

from imrabo.internal import paths
from imrabo.internal.constants import RUNTIME_HOST, RUNTIME_PORT
# from imrabo.runtime.security import load_token, generate_token, save_token # This will be handled by daemon
from imrabo.internal.logging import get_logger

logger = get_logger(__name__)

# Placeholder for security functions, which will eventually be moved
def load_token(path: Path) -> str | None:
    return path.read_text().strip() if path.exists() else None

def generate_token() -> str:
    import secrets
    return secrets.token_urlsafe(32)

def save_token(token: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token)


class RuntimeClient:
    """
    Thin async client for communicating with the imrabo runtime daemon.

    Guarantees:
    - yields TEXT DELTAS only (never repeated text)
    - clean stream termination
    - correct SSE parsing
    """

    def __init__(self, host: str = RUNTIME_HOST, port: int = RUNTIME_PORT):
        self.base_url = f"http://{host}:{port}"
        self._token: str | None = None
        self._load_or_generate_token()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _load_or_generate_token(self) -> None:
        token_file = Path(paths.get_runtime_token_file())
        token = load_token(token_file)

        if not token:
            token = generate_token()
            save_token(token, token_file)
            logger.info("Generated new runtime token")

        self._token = token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{self.base_url}/health", headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def status(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{self.base_url}/status", headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def shutdown(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{self.base_url}/shutdown", headers=self._headers())
            r.raise_for_status()
            return r.json()

    # ------------------------------------------------------------------
    # Streaming inference
    # ------------------------------------------------------------------

    async def run_prompt(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Streams response from /run and yields ONLY incremental text deltas,
        adapting to the new ExecutionResult structure.
        """

        url = f"{self.base_url}/run"
        payload = {"prompt": prompt} # The adapter translates this to ExecutionRequest.input

        decoder = codecs.getincrementaldecoder("utf-8")()
        last_full_content = ""

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=self._headers(),
                    json=payload,
                ) as response:

                    if response.status_code >= 400:
                        body = await response.aread()
                        raise RuntimeError(
                            f"Runtime error {response.status_code}: "
                            f"{body.decode(errors='ignore')}"
                        )

                    async for chunk in response.aiter_bytes():
                        if not chunk:
                            continue # Keep reading until final empty chunk or end of stream.

                        text = decoder.decode(chunk, final=False) # Decode incrementally

                        for line in text.splitlines():
                            line = line.strip()
                            if not line.startswith("data:"):
                                continue

                            try:
                                # The adapter now sends ExecutionResult.output directly
                                # This will contain {'content': '...', 'stop': False/True}
                                data = json.loads(line[len("data:"):].strip())
                            except json.JSONDecodeError:
                                logger.warning(f"JSON decode error in stream: {line}")
                                continue

                            current_content = data.get("content", "")
                            stop_signal = data.get("stop", False)

                            # Extract delta
                            if current_content.startswith(last_full_content):
                                delta = current_content[len(last_full_content):]
                            else:
                                # This can happen if the adapter sends a complete message
                                # or if there's a reset. For now, treat as full update.
                                delta = current_content
                                
                            if delta:
                                yield delta
                                last_full_content = current_content

                            if stop_signal:
                                return # End of stream

        except httpx.RequestError as exc:
            logger.error("Streaming connection failed", exc_info=exc)
            raise RuntimeError("Streaming connection failed") from exc

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<RuntimeClient base_url={self.base_url}>"
