import typer
import asyncio
from pathlib import Path
import sys # For Python version check
import json

from imrabo.internal import paths
from imrabo.internal.logging import get_logger
# from imrabo.runtime import system # This module no longer exists
from imrabo.cli.client import RuntimeClient
from imrabo.adapters.storage_fs import FileSystemArtifactResolver # New resolver

logger = get_logger(__name__)

def doctor():
    """
    Check the imrabo installation and system health.
    """
    typer.echo("Running imrabo doctor checks...\n")
    all_passed = True

    def check(description: str, func):
        nonlocal all_passed
        typer.echo(f"- {description}...", nl=False)
        result, message = func()
        if result:
            typer.echo(f" {typer.style('PASSED', fg=typer.colors.GREEN)}")
        else:
            typer.echo(f" {typer.style('FAILED', fg=typer.colors.RED)}")
            typer.echo(f"  Reason: {message}")
            all_passed = False

    # --- System Checks ---
    typer.echo(typer.style("System Information:", fg=typer.colors.BLUE, bold=True))
    typer.echo(f"  Python Version: {sys.version.split()[0]}")
    typer.echo("")

    # --- Runtime Status ---
    typer.echo(typer.style("Runtime Status:", fg=typer.colors.BLUE, bold=True))
    client = RuntimeClient()
    try:
        async def get_runtime_status():
            return await client.status()
        
        runtime_response = asyncio.run(get_runtime_status())
        if runtime_response.get('status') == 'ok_from_kernel': # Updated status check based on FastAPI adapter placeholder
            typer.echo(f"  Runtime API: {typer.style('Accessible', fg=typer.colors.GREEN)}")
            typer.echo(f"  Full Status: {json.dumps(runtime_response, indent=2)}")
        else:
            typer.echo(f"  Runtime API: {typer.style('Not Running or Unresponsive', fg=typer.colors.YELLOW)}")
            all_passed = False
    except Exception as e:
        typer.echo(f"  Runtime API: {typer.style('Not Accessible', fg=typer.colors.RED)}")
        typer.echo(f"  Reason: {e}")
        all_passed = False
    typer.echo("")

    # --- Local Filesystem Checks ---
    typer.echo(typer.style("Local Filesystem Checks:", fg=typer.colors.BLUE, bold=True))

    def check_app_data_dir():
        app_dir = Path(paths.get_app_data_dir())
        return app_dir.is_dir(), f"Directory '{app_dir}' not found or not a directory."
    check("App data directory", check_app_data_dir)

    def check_pid_file():
        pid_file = Path(paths.get_runtime_pid_file())
        return pid_file.exists(), f"PID file '{pid_file}' not found."
    check("Runtime PID file", check_pid_file)

    def check_token_file():
        token_file = Path(paths.get_runtime_token_file())
        return token_file.exists() and token_file.stat().st_size > 0, f"Token file '{token_file}' not found or empty."
    check("Runtime token file", check_token_file)
    
    # --- LLM Engine Specific Checks ---
    typer.echo(typer.style("\nLLM Engine Checks:", fg=typer.colors.BLUE, bold=True))

    def check_llama_cpp_import():
        try:
            import llama_cpp
            return True, ""
        except ImportError:
            return False, "The 'llama_cpp' library is not installed or accessible. Please run `pip install llama-cpp-python`."
    check("llama-cpp-python import", check_llama_cpp_import)

    def check_model_availability():
        registry_path = Path(__file__).parent.parent.parent / "registry" / "models.json"
        models_dir = Path(paths.get_models_dir())
        resolver = FileSystemArtifactResolver(registry_path=registry_path, models_dir=models_dir)
        
        available_models = resolver.list_available()
        if available_models:
            return True, f"Found {len(available_models)} installed model(s)."
        else:
            return False, "No models found or installed. Please run `imrabo install`."
    check("Model presence and integrity", check_model_availability)


    typer.echo("\n--- Doctor Check Summary ---")
    if all_passed:
        typer.echo(typer.style("All checks PASSED!", fg=typer.colors.GREEN, bold=True))
        return typer.Exit(0)
    else:
        typer.echo(typer.style("Some checks FAILED. Please review the output above.", fg=typer.colors.RED, bold=True))
        return typer.Exit(1)

if __name__ == "__main__":
    typer.run(doctor)
