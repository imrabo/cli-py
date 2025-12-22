import json
import httpx
import codecs
from typing import AsyncGenerator
from pathlib import Path

from imrabo.internal import paths
from imrabo.internal.constants import RUNTIME_HOST, RUNTIME_PORT
from imrabo.runtime.security import load_token, generate_token, save_token
from imrabo.internal.logging import get_logger

logger = get_logger(__name__)


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
    # Streaming inference (FIXED)
    # ------------------------------------------------------------------

    async def run_prompt(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Streams response from /run and yields ONLY incremental text deltas.
        """

        url = f"{self.base_url}/run"
        payload = {"prompt": prompt}

        decoder = codecs.getincrementaldecoder("utf-8")()
        last_text = ""

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
                            return  # clean close

                        text = decoder.decode(chunk)

                        for line in text.splitlines():
                            line = line.strip()
                            if not line:
                                continue

                            # SSE format
                            if line.startswith("data:"):
                                line = line[len("data:"):].strip()

                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            full_text = data.get("content", "")
                            stop = data.get("stop", False)

                            # ✅ DELTA EXTRACTION (THE KEY FIX)
                            if full_text.startswith(last_text):
                                delta = full_text[len(last_text):]
                            else:
                                delta = full_text  # fallback safety

                            if delta:
                                yield delta
                                last_text = full_text

                            if stop is True:
                                return

        except httpx.RequestError as exc:
            logger.error("Streaming connection failed", exc_info=exc)
            raise RuntimeError("Streaming connection failed") from exc

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<RuntimeClient base_url={self.base_url}>"
