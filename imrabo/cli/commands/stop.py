import typer
import os
import signal
import time # Added for sleep
from pathlib import Path
import asyncio

from imrabo.internal import paths
from imrabo.internal.logging import configure_logging
from imrabo.cli.client import RuntimeClient

logger = configure_logging()

def _remove_pid_file():
    pid_file = Path(paths.get_runtime_pid_file())
    if pid_file.exists():
        pid_file.unlink()
        logger.info(f"Removed PID file: {pid_file}")

def _get_pid_from_file() -> int | None:
    pid_file = Path(paths.get_runtime_pid_file())
    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                return int(f.read().strip())
        except ValueError:
            logger.warning(f"Corrupted PID file found: {pid_file}. Deleting it.")
            pid_file.unlink()
            return None
    return None

def stop():
    """
    Stop the imrabo runtime.
    """
    typer.echo("Attempting to stop imrabo runtime...")
    client = RuntimeClient()
    
    # Try graceful shutdown via API
    try:
        async def do_api_shutdown():
            response = await client.shutdown()
            return response
        
        response = asyncio.run(do_api_shutdown())
        if response.get("message") == "Shutting down":
            typer.echo("Runtime gracefully shut down via API.")
            _remove_pid_file()
            return typer.Exit(0)
    except Exception as e:
        logger.warning(f"API shutdown failed: {e}. Falling back to PID termination.")
        typer.echo(f"API shutdown failed: {e}. Falling back to PID termination.")

    # Fallback: terminate process using PID file
    pid = _get_pid_from_file()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            typer.echo(f"Sent SIGTERM to runtime process with PID {pid}.")
            # Give it a moment to terminate
            time.sleep(2) 
            # Check if process is still alive
            try:
                os.kill(pid, 0) # Signal 0 doesn't kill, just checks existence
                typer.echo(f"Process {pid} is still alive. Sending SIGKILL.")
                os.kill(pid, signal.SIGKILL)
                typer.echo(f"Sent SIGKILL to runtime process with PID {pid}.")
            except OSError:
                typer.echo(f"Process {pid} terminated successfully.")
            _remove_pid_file()
            return typer.Exit(0)
        except ProcessLookupError:
            typer.echo(f"No active process found with PID {pid}. PID file might be stale.")
            _remove_pid_file()
            return typer.Exit(0)
        except Exception as e:
            typer.echo(f"Error terminating process with PID {pid}: {e}")
            logger.error(f"Error terminating process with PID {pid}: {e}")
            return typer.Exit(1)
    else:
        typer.echo("No imrabo runtime PID file found. Is the runtime running?")
        return typer.Exit(1)

if __name__ == "__main__":
    typer.run(stop)
