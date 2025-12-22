# import json
# from imrabo.engine.base import LLMEngine
# import subprocess
# import os
# import time
# import requests
# from pathlib import Path
# from requests.exceptions import HTTPError, ConnectionError
# from imrabo.internal import paths
# from imrabo.internal.logging import get_logger

# class LlamaBinaryEngine(LLMEngine):
#     """
#     Implementation of the LLMEngine interface to manage a llama.cpp binary (llama-server.exe).
#     """
#     SERVER_HOST = "127.0.0.1"
#     SERVER_PORT = 8080
#     SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
#     HEALTH_ENDPOINT = f"{SERVER_URL}/health"
#     INFER_ENDPOINT = f"{SERVER_URL}/completion" # Assuming /completion endpoint for inference

#     def __init__(self, model_path: Path): # Corrected type hint
#         self.logger = get_logger(self.__class__.__name__)
#         self.model_path = model_path
#         self.process: subprocess.Popen | None = None
#         self.pid: int | None = None
#         self.server_ready = False

#     def load(self):
#         """
#         Loads the llama.cpp binary (llama-server.exe) and starts it as a detached subprocess.
#         It then polls the server's health endpoint to ensure it's ready for requests.
#         """
#         llama_server_path = Path(paths.get_llama_server_binary_path())
#         if not llama_server_path.exists():
#             raise FileNotFoundError(f"llama-server.exe not found at {llama_server_path}. "
#                                     "Please ensure it is downloaded and placed there.")

#         self.logger.info(f"Starting llama-server from: {llama_server_path}")
#         self.logger.info(f"Using model: {self.model_path}")

#         command = [
#             str(llama_server_path),
#             "-m", str(self.model_path),
#             "-h", self.SERVER_HOST,
#             "-p", str(self.SERVER_PORT),
#             "--port", str(self.SERVER_PORT), # --port is an alias for -p, good for clarity
#             "--silent", # Reduce verbosity for server output
#         ]

#         # Start as a detached subprocess
#         # On Windows, creationflags=subprocess.DETACHED_PROCESS and close_fds=True
#         # help in detaching the process from the parent.
#         try:
#             self.process = subprocess.Popen(
#                 command,
#                 stdout=subprocess.DEVNULL, # Redirect stdout to DEVNULL to prevent blocking
#                 stderr=subprocess.DEVNULL, # Redirect stderr to DEVNULL
#                 creationflags=subprocess.DETACHED_PROCESS,
#                 close_fds=True # Close file descriptors inherited by the child process
#             )
#             self.pid = self.process.pid
#             self.logger.info(f"llama-server started with PID: {self.pid}")
#         except Exception as e:
#             self.logger.exception(f"Failed to start llama-server process: {e}")
#             raise RuntimeError(f"Failed to start llama-server process: {e}")

#         # Poll health endpoint until server is ready
#         self.logger.info(f"Polling llama-server at {self.HEALTH_ENDPOINT} for readiness...")
#         max_retries = 30
#         retry_delay = 1 # seconds
#         for i in range(max_retries):
#             try:
#                 response = requests.get(self.HEALTH_ENDPOINT, timeout=1)
#                 response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
#                 if response.json().get("status") == "ok":
#                     self.server_ready = True
#                     self.logger.info("llama-server is ready.")
#                     return
#             except (ConnectionError, HTTPError) as e:
#                 self.logger.debug(f"Attempt {i+1}/{max_retries}: llama-server not ready yet ({e}). Retrying in {retry_delay}s...")
#             except Exception as e:
#                 self.logger.warning(f"Unexpected error while polling llama-server health: {e}")
#             time.sleep(retry_delay)
        
#         self.logger.error("llama-server did not become ready within the allotted time.")
#         self.unload() # Attempt to clean up
#         raise RuntimeError("llama-server failed to start or become ready.")

#     def unload(self):
#         """
#         Unloads the llama.cpp binary and terminates the process.
#         """
#         if self.process and self.process.poll() is None:  # Check if process exists and is still running
#             self.logger.info(f"Attempting to terminate llama-server process with PID: {self.pid}")
#             try:
#                 self.process.terminate()  # Send SIGTERM on POSIX, WM_CLOSE on Windows
#                 self.process.wait(timeout=5)  # Wait for process to terminate, 5 seconds timeout
#                 if self.process.poll() is None:
#                     self.logger.warning(f"llama-server process {self.pid} did not terminate gracefully, killing it.")
#                     self.process.kill()  # Force kill if not terminated
#                 self.logger.info(f"llama-server process {self.pid} terminated.")
#             except Exception as e:
#                 self.logger.exception(f"Error terminating llama-server process {self.pid}: {e}")
#             finally:
#                 self.process = None
#                 self.pid = None
#                 self.server_ready = False
#         else:
#             self.logger.info("llama-server process is not running or already terminated.")

#     def infer(self, prompt: str, stream_cb=None) -> None:
#         """
#         Sends a prompt to the llama.cpp binary's /completion endpoint for inference,
#         streaming tokens back to the caller via a callback.
#         """
#         if not self.server_ready:
#             raise RuntimeError("llama-server is not ready. Call load() first.")

#         # Default parameters from llama.cpp server's defaults, can be made configurable
#         payload = {
#             "prompt": prompt,
#             "n_predict": 512,
#             "temperature": 0.7,
#             "stream": True,
#         }

#         try:
#             with requests.post(self.INFER_ENDPOINT, json=payload, stream=True, timeout=60) as response:
#                 response.raise_for_status()
#                 for chunk in response.iter_content(chunk_size=None): # Process chunks as they arrive
#                     if chunk:
#                         # llama-server streams in SSE format (data: {json}\n\n)
#                         # We need to parse each line
#                         for line in chunk.decode('utf-8').splitlines():
#                             if line.startswith("data:"):
#                                 try:
#                                     json_data = json.loads(line[len("data:"):].strip())
#                                     content = json_data.get("content")
#                                     if content and stream_cb:
#                                         stream_cb(content)
                                    
#                                     # Check for stop signal from the server
#                                     if json_data.get("stop"):
#                                         return

#                                 except json.JSONDecodeError as e:
#                                     self.logger.warning(f"JSON decode error in stream: {e} - Line: {line}")
#                                     continue
                        
#         except ConnectionError as e:
#             self.logger.error(f"Failed to connect to llama-server for inference: {e}")
#             raise RuntimeError(f"Connection to llama-server failed: {e}")
#         except HTTPError as e:
#             self.logger.error(f"llama-server returned HTTP error during inference: {e.response.status_code} - {e.response.text}")
#             raise RuntimeError(f"llama-server HTTP error: {e.response.status_code}")
#         except requests.Timeout:
#             self.logger.error("Inference request timed out.")
#             raise RuntimeError("Inference request timed out.")
#         except Exception as e:
#             self.logger.exception(f"Unexpected error during inference: {e}")
#             raise RuntimeError(f"Unexpected error during inference: {e}")

#     def health(self) -> dict:
#         """
#         Checks the health/status of the running llama.cpp binary.
#         """
#         status_data = {
#             "engine": "llama.cpp",
#             "pid": self.pid,
#             "model": self.model_path.name if self.model_path else None,
#             "status": "uninitialized"
#         }

#         if not self.server_ready:
#             status_data["status"] = "not_ready"
#             return status_data

#         try:
#             response = requests.get(self.HEALTH_ENDPOINT, timeout=1)
#             response.raise_for_status()
#             health_response = response.json()
#             if health_response.get("status") == "ok":
#                 status_data["status"] = "ready"
#             else:
#                 status_data["status"] = "error"
#                 status_data["details"] = health_response
#         except ConnectionError:
#             status_data["status"] = "unreachable"
#             self.logger.warning(f"llama-server at {self.HEALTH_ENDPOINT} is unreachable.")
#         except HTTPError as e:
#             status_data["status"] = "http_error"
#             status_data["details"] = str(e)
#             self.logger.warning(f"llama-server at {self.HEALTH_ENDPOINT} returned HTTP error: {e}")
#         except Exception as e:
#             status_data["status"] = "unknown_error"
#             status_data["details"] = str(e)
#             self.logger.exception(f"Unexpected error during llama-server health check: {e}")

#         return status_data

import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Callable

import requests
from requests.exceptions import ConnectionError, HTTPError

from imrabo.engine.base import LLMEngine
from imrabo.internal import paths
from imrabo.internal.logging import get_logger


class LlamaBinaryEngine(LLMEngine):
    """
    Manages a llama.cpp llama-server binary as an external inference engine.
    """

    SERVER_HOST = "127.0.0.1"
    SERVER_PORT = 8080

    SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
    HEALTH_ENDPOINT = f"{SERVER_URL}/health"
    INFER_ENDPOINT = f"{SERVER_URL}/completion"

    def __init__(self, model_path: Path):
        self.logger = get_logger(self.__class__.__name__)
        self.model_path = model_path

        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.server_ready: bool = False

    # ---------------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------------

    def load(self) -> None:
        llama_server_path = Path(paths.get_llama_server_binary_path())
        if not llama_server_path.exists():
            raise FileNotFoundError(f"llama-server.exe not found at {llama_server_path}")

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        command = [
            str(llama_server_path),
            "-m", str(self.model_path),
            "--port", str(self.SERVER_PORT),
        ]

        self.logger.info("Starting llama-server", extra={
            "binary": str(llama_server_path),
            "model": str(self.model_path),
            "port": self.SERVER_PORT,
        })

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=open(paths.get_llama_log_file(), "ab"),
                creationflags=subprocess.DETACHED_PROCESS,
                close_fds=True,
            )
            self.pid = self.process.pid
        except Exception as e:
            self.logger.exception("Failed to start llama-server")
            raise RuntimeError(f"Failed to start llama-server: {e}")

        self._wait_for_ready()

    def unload(self) -> None:
        if not self.process:
            return

        if self.process.poll() is None:
            self.logger.info("Stopping llama-server", extra={"pid": self.pid})
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.logger.warning("Graceful shutdown failed, killing process")
                self.process.kill()
            finally:
                self.process = None
                self.pid = None
                self.server_ready = False

    # ---------------------------------------------------------------------
    # Readiness
    # ---------------------------------------------------------------------

    def _wait_for_ready(self) -> None:
        max_retries = 30
        delay = 1.0

        for attempt in range(max_retries):
            try:
                r = requests.get(self.HEALTH_ENDPOINT, timeout=1)
                r.raise_for_status()

                # IMPORTANT: probe completion, not just health
                probe = {
                    "prompt": " ",
                    "n_predict": 1,
                }
                p = requests.post(self.INFER_ENDPOINT, json=probe, timeout=3)
                p.raise_for_status()

                self.server_ready = True
                self.logger.info("llama-server is ready")
                return

            except Exception as e:
                self.logger.debug(
                    f"llama-server not ready ({attempt + 1}/{max_retries})",
                    extra={"error": str(e)},
                )
                time.sleep(delay)

        self.unload()
        raise RuntimeError("llama-server failed to become ready")

    # ---------------------------------------------------------------------
    # Inference
    # ---------------------------------------------------------------------

    def infer(self, prompt: str, stream_cb: Optional[Callable[[str], None]] = None) -> None:
        if not self.server_ready:
            raise RuntimeError("llama-server is not ready")

        payload = {
            "prompt": prompt,
            "n_predict": 512,
            "temperature": 0.7,
            "stream": True,
        }

        try:
            with requests.post(
                self.INFER_ENDPOINT,
                json=payload,
                stream=True,
                timeout=60,
            ) as response:
                response.raise_for_status()

                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue

                    line = line.strip()
                    if line.startswith("data:"):
                        line = line[len("data:"):].strip()

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if content := data.get("content"):
                        if stream_cb:
                            stream_cb(content)

                    if data.get("stop"):
                        return

        except ConnectionError as e:
            self.logger.error("Connection to llama-server failed", exc_info=e)
            raise RuntimeError("Connection to llama-server failed")

        except HTTPError as e:
            self.logger.error(
                "llama-server HTTP error",
                extra={"status": e.response.status_code, "body": e.response.text},
            )
            raise RuntimeError(f"llama-server HTTP error {e.response.status_code}")

        except Exception as e:
            self.logger.exception("Unexpected inference error")
            raise RuntimeError(f"Unexpected inference error: {e}")

    # ---------------------------------------------------------------------
    # Health
    # ---------------------------------------------------------------------

    def health(self) -> dict:
        status = {
            "engine": "llama.cpp",
            "pid": self.pid,
            "model": self.model_path.name,
            "status": "unknown",
        }

        if not self.server_ready:
            status["status"] = "not_ready"
            return status

        try:
            r = requests.get(self.HEALTH_ENDPOINT, timeout=1)
            r.raise_for_status()
            status["status"] = "ready"
        except Exception:
            status["status"] = "unreachable"

        return status
