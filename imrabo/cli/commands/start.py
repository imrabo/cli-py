import typer
import subprocess
import sys
import time
import os
from pathlib import Path
import asyncio

from imrabo.internal import paths
from imrabo.internal.logging import configure_logging
from imrabo.internal.constants import RUNTIME_HOST, RUNTIME_PORT
from imrabo.cli.client import RuntimeClient

logger = configure_logging()

def _is_runtime_active(client: RuntimeClient) -> bool:
    try:
        async def check_health():
            try:
                response = await client.health()
                return response.get("status") == "ok"
            except Exception:
                return False
        
        return asyncio.run(check_health())

    except Exception:
        return False

def _save_pid(pid: int):
    pid_file = Path(paths.get_runtime_pid_file())
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    with open(pid_file, "w") as f:
        f.write(str(pid))
    logger.info(f"Runtime PID {pid} saved to {pid_file}")

def _get_saved_pid() -> int | None:
    pid_file = Path(paths.get_runtime_pid_file())
    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                return int(f.read().strip())
        except ValueError:
            pid_file.unlink() # Corrupted PID file
            return None
    return None

def start():
    """
    Start the imrabo runtime.
    """
    client = RuntimeClient()
    if _is_runtime_active(client):
        typer.echo("imrabo runtime is already running.")
        return typer.Exit(0)

    typer.echo("Starting imrabo runtime...")
    
    # Path to the runtime server module
    # Assuming imrabo is installed or run in editable mode,
    # python -m imrabo.runtime.server should work.
    
    python_executable = sys.executable

    command = [
        python_executable, 
        "-m", "imrabo.runtime.server" # This tells python to run the server.py as a module
    ]

    # Detach the process
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS
        preexec_fn = None
    else:
        creationflags = 0
        preexec_fn = os.setsid

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            preexec_fn=preexec_fn,
            creationflags=creationflags,
            close_fds=True 
        )
        _save_pid(process.pid)
        logger.info(f"imrabo runtime initiated with PID {process.pid}")

        typer.echo("Waiting for runtime to become active...")
        for _ in range(30): # Wait up to 30 seconds
            if _is_runtime_active(client):
                typer.echo(f"imrabo runtime started successfully at {client.base_url}")
                # On Windows, prevent the Popen destructor from running on the detached process handle
                if sys.platform == "win32":
                    process._handle = None
                return typer.Exit(0)
            time.sleep(1)
        
        typer.echo("Error: imrabo runtime failed to start within the timeout period.")
        return typer.Exit(1)

    except Exception as e:
        typer.echo(f"Failed to start imrabo runtime: {e}")
        logger.error(f"Failed to start imrabo runtime: {e}")
        return typer.Exit(1)

if __name__ == "__main__":
    typer.run(start)
