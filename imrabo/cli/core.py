# """
# Core, reusable logic for CLI commands, decoupled from Typer.
# """
# import asyncio
# import os
# import signal
# import subprocess
# import sys
# import time
# from pathlib import Path

# from imrabo.cli.client import RuntimeClient
# from imrabo.internal import paths
# from imrabo.internal.logging import get_logger

# logger = get_logger()

# def is_runtime_active(client: RuntimeClient) -> bool:
#     """Check if the runtime is active and responsive."""
#     try:
#         async def check():
#             return (await client.health()).get("status") == "ok"
#         return asyncio.run(check())
#     except Exception:
#         return False

# def save_pid(pid: int):
#     """Save a process ID to the runtime PID file."""
#     pid_file = Path(paths.get_runtime_pid_file())
#     pid_file.parent.mkdir(parents=True, exist_ok=True)
#     with open(pid_file, "w") as f:
#         f.write(str(pid))
#     logger.info("Runtime PID saved", pid=pid, path=str(pid_file))

# def get_saved_pid() -> int | None:
#     """Get the saved process ID from the runtime PID file."""
#     pid_file = Path(paths.get_runtime_pid_file())
#     if not pid_file.exists():
#         return None
#     try:
#         with open(pid_file, "r") as f:
#             return int(f.read().strip())
#     except (ValueError, IOError):
#         logger.warning("Corrupted PID file found, deleting.", path=str(pid_file))
#         pid_file.unlink()
#         return None

# def remove_pid_file():
#     """Remove the runtime PID file."""
#     pid_file = Path(paths.get_runtime_pid_file())
#     if pid_file.exists():
#         pid_file.unlink()
#         logger.info("Removed PID file", path=str(pid_file))

# def start_runtime() -> bool:
#     """
#     Core logic to start the runtime server as a background process.
#     Returns True on success, False on failure.
#     """
#     client = RuntimeClient()
#     if is_runtime_active(client):
#         logger.info("start_runtime requested but runtime is already active.")
#         return True # Already running is a success condition for the caller

#     logger.info("Starting imrabo runtime process...")
#     python_executable = sys.executable
#     command = [python_executable, "-m", "imrabo.runtime.server"]

#     creationflags = subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
#     preexec_fn = None if sys.platform == "win32" else os.setsid

#     try:
#         process = subprocess.Popen(
#             command,
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.DEVNULL,
#             creationflags=creationflags,
#             preexec_fn=preexec_fn,
#             close_fds=True,
#         )
#         save_pid(process.pid)
#         logger.info("imrabo runtime process initiated", pid=process.pid)

#         # Wait for the runtime to become active
#         for _ in range(30):
#             if is_runtime_active(client):
#                 logger.info("Runtime confirmed active", base_url=client.base_url)
#                 return True
#             time.sleep(1)

#         logger.error("Runtime failed to start within the timeout period.")
#         return False
#     except Exception as e:
#         logger.error("Failed to start imrabo runtime process", exc_info=e)
#         return False

# def stop_runtime() -> bool:
#     """
#     Core logic to stop the runtime server.
#     Tries graceful shutdown via API, then falls back to PID kill.
#     Returns True on success, False on failure.
#     """
#     client = RuntimeClient()
    
#     # Try graceful shutdown
#     try:
#         logger.info("Attempting graceful shutdown via API.")
#         asyncio.run(client.shutdown())
#         logger.info("Runtime gracefully shut down via API.")
#         remove_pid_file()
#         return True
#     except Exception as e:
#         logger.warning(
#             "API shutdown failed, falling back to PID termination.",
#             error=str(e),
#         )

#     # Fallback to PID kill
#     pid = get_saved_pid()
#     if not pid:
#         logger.warning("No runtime PID file found. Assuming runtime is not running.")
#         return True # Not running is a success condition for stop

#     try:
#         logger.info("Terminating runtime process via PID.", pid=pid)
#         os.kill(pid, signal.SIGTERM)
#         time.sleep(2) # Wait for termination
#         os.kill(pid, 0) # Check if still alive
#         logger.warning("Process did not terminate gracefully. Sending SIGKILL.", pid=pid)
#         os.kill(pid, signal.SIGKILL)
#     except ProcessLookupError:
#         logger.info("Process not found, was already stopped.", pid=pid)
#     except OSError: # This can happen if the process terminated between the two kill signals
#         logger.info("Process terminated successfully after SIGTERM.", pid=pid)
#     except Exception as e:
#         logger.error("Failed to terminate process.", pid=pid, exc_info=e)
#         return False
#     finally:
#         remove_pid_file()
    
#     return True


"""
Core, reusable logic for CLI commands.
Responsible ONLY for runtime process lifecycle.
"""

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from imrabo.cli.client import RuntimeClient
from imrabo.internal import paths
from imrabo.internal.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------
# Async helper (CRITICAL)
# ---------------------------------------------------------------------

def run_async(coro):
    """
    Safely run an async coroutine from sync code.
    Works whether an event loop exists or not.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        return loop.run_until_complete(coro)

# ---------------------------------------------------------------------
# Runtime health (API reachability ONLY)
# ---------------------------------------------------------------------

def is_runtime_active(client: RuntimeClient) -> bool:
    """
    Check whether the runtime API is reachable.
    This MUST NOT depend on engine readiness.
    """
    try:
        async def check():
            health = await client.health()
            return isinstance(health, dict) and "status" in health

        return run_async(check())
    except Exception:
        return False

# ---------------------------------------------------------------------
# PID file helpers
# ---------------------------------------------------------------------

def save_pid(pid: int) -> None:
    pid_file = Path(paths.get_runtime_pid_file())
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid))
    logger.info("Runtime PID saved", pid=pid, path=str(pid_file))


def get_saved_pid() -> Optional[int]:
    pid_file = Path(paths.get_runtime_pid_file())
    if not pid_file.exists():
        return None

    try:
        return int(pid_file.read_text().strip())
    except Exception:
        logger.warning("Corrupted PID file detected, removing", path=str(pid_file))
        pid_file.unlink(missing_ok=True)
        return None


def remove_pid_file() -> None:
    pid_file = Path(paths.get_runtime_pid_file())
    if pid_file.exists():
        pid_file.unlink()
        logger.info("Removed runtime PID file", path=str(pid_file))

# ---------------------------------------------------------------------
# Runtime lifecycle
# ---------------------------------------------------------------------

def start_runtime() -> bool:
    """
    Start the runtime server as a detached background process.
    Idempotent: returns True if already running.
    """
    client = RuntimeClient()

    if is_runtime_active(client):
        logger.info("Runtime already active")
        return True

    logger.info("Starting imrabo runtime process")

    python_exec = sys.executable
    # Point to the new adapter and remove model/variant args
    command = [python_exec, "-m", "imrabo.adapters.http.fastapi_server"]

    creationflags = subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
    preexec_fn = None if sys.platform == "win32" else os.setsid

    try:
        process = subprocess.Popen(
            command,
            creationflags=creationflags,
            preexec_fn=preexec_fn,
            close_fds=True,
        )

        save_pid(process.pid)
        logger.info("Runtime process spawned", pid=process.pid)

        # Wait up to 30s for API to come up
        for _ in range(30):
            if is_runtime_active(client):
                logger.info("Runtime confirmed active", base_url=client.base_url)
                return True
            time.sleep(1)

        logger.error("Runtime did not become active within timeout")
        return False

    except Exception as e:
        logger.exception("Failed to start runtime", exc_info=e)
        return False

# ---------------------------------------------------------------------
# Stop runtime
# ---------------------------------------------------------------------

def stop_runtime() -> bool:
    """
    Stop the runtime server.
    Graceful API shutdown first, PID kill fallback.
    """
    client = RuntimeClient()

    # Attempt graceful shutdown
    try:
        logger.info("Attempting graceful shutdown via API")
        run_async(client.shutdown())
        remove_pid_file()
        logger.info("Runtime shut down gracefully")
        return True
    except Exception as e:
        logger.warning("API shutdown failed, falling back to PID", error=str(e))

    pid = get_saved_pid()
    if not pid:
        logger.info("No runtime PID found; runtime not running")
        return True

    try:
        logger.info("Sending SIGTERM to runtime", pid=pid)
        os.kill(pid, signal.SIGTERM)
        time.sleep(2)

        # Check if still alive
        os.kill(pid, 0)
        logger.warning("Runtime still alive, sending SIGKILL", pid=pid)
        os.kill(pid, signal.SIGKILL)

    except ProcessLookupError:
        logger.info("Runtime already stopped", pid=pid)
    except Exception as e:
        logger.error("Failed to terminate runtime", pid=pid, exc_info=e)
        return False
    finally:
        remove_pid_file()

    return True
