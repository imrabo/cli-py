"""
Core, reusable logic for CLI commands, decoupled from Typer.
"""
import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from imrabo.cli.client import RuntimeClient
from imrabo.internal import paths
from imrabo.internal.logging import get_logger

logger = get_logger()

def is_runtime_active(client: RuntimeClient) -> bool:
    """Check if the runtime is active and responsive."""
    try:
        async def check():
            return (await client.health()).get("status") == "ok"
        return asyncio.run(check())
    except Exception:
        return False

def save_pid(pid: int):
    """Save a process ID to the runtime PID file."""
    pid_file = Path(paths.get_runtime_pid_file())
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    with open(pid_file, "w") as f:
        f.write(str(pid))
    logger.info("Runtime PID saved", pid=pid, path=str(pid_file))

def get_saved_pid() -> int | None:
    """Get the saved process ID from the runtime PID file."""
    pid_file = Path(paths.get_runtime_pid_file())
    if not pid_file.exists():
        return None
    try:
        with open(pid_file, "r") as f:
            return int(f.read().strip())
    except (ValueError, IOError):
        logger.warning("Corrupted PID file found, deleting.", path=str(pid_file))
        pid_file.unlink()
        return None

def remove_pid_file():
    """Remove the runtime PID file."""
    pid_file = Path(paths.get_runtime_pid_file())
    if pid_file.exists():
        pid_file.unlink()
        logger.info("Removed PID file", path=str(pid_file))

def start_runtime() -> bool:
    """
    Core logic to start the runtime server as a background process.
    Returns True on success, False on failure.
    """
    client = RuntimeClient()
    if is_runtime_active(client):
        logger.info("start_runtime requested but runtime is already active.")
        return True # Already running is a success condition for the caller

    logger.info("Starting imrabo runtime process...")
    python_executable = sys.executable
    command = [python_executable, "-m", "imrabo.runtime.server"]

    creationflags = subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
    preexec_fn = None if sys.platform == "win32" else os.setsid

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            preexec_fn=preexec_fn,
            close_fds=True,
        )
        save_pid(process.pid)
        logger.info("imrabo runtime process initiated", pid=process.pid)

        # Wait for the runtime to become active
        for _ in range(30):
            if is_runtime_active(client):
                logger.info("Runtime confirmed active", base_url=client.base_url)
                if sys.platform == "win32":
                    process._handle = None # Prevent OSError on Windows exit
                return True
            time.sleep(1)

        logger.error("Runtime failed to start within the timeout period.")
        return False
    except Exception as e:
        logger.error("Failed to start imrabo runtime process", exc_info=e)
        return False

def stop_runtime() -> bool:
    """
    Core logic to stop the runtime server.
    Tries graceful shutdown via API, then falls back to PID kill.
    Returns True on success, False on failure.
    """
    client = RuntimeClient()
    
    # Try graceful shutdown
    try:
        logger.info("Attempting graceful shutdown via API.")
        asyncio.run(client.shutdown())
        logger.info("Runtime gracefully shut down via API.")
        remove_pid_file()
        return True
    except Exception as e:
        logger.warning(
            "API shutdown failed, falling back to PID termination.",
            error=str(e),
        )

    # Fallback to PID kill
    pid = get_saved_pid()
    if not pid:
        logger.warning("No runtime PID file found. Assuming runtime is not running.")
        return True # Not running is a success condition for stop

    try:
        logger.info("Terminating runtime process via PID.", pid=pid)
        os.kill(pid, signal.SIGTERM)
        time.sleep(2) # Wait for termination
        os.kill(pid, 0) # Check if still alive
        logger.warning("Process did not terminate gracefully. Sending SIGKILL.", pid=pid)
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        logger.info("Process not found, was already stopped.", pid=pid)
    except OSError: # This can happen if the process terminated between the two kill signals
        logger.info("Process terminated successfully after SIGTERM.", pid=pid)
    except Exception as e:
        logger.error("Failed to terminate process.", pid=pid, exc_info=e)
        return False
    finally:
        remove_pid_file()
    
    return True
