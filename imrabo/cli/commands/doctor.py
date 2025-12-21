import typer
import asyncio
from pathlib import Path

from imrabo.internal import paths
from imrabo.internal.logging import configure_logging
from imrabo.runtime import system
from imrabo.cli.client import RuntimeClient
from imrabo.runtime.model_manager import ModelManager # To perform local checks

logger = configure_logging()

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
    typer.echo(f"  OS: {system.get_os_info()}")
    typer.echo(f"  Architecture: {system.get_cpu_arch()}")
    typer.echo(f"  Total RAM: {system.get_total_ram_gb()} GB")
    typer.echo("")

    # --- Runtime Status ---
    typer.echo(typer.style("Runtime Status:", fg=typer.colors.BLUE, bold=True))
    client = RuntimeClient()
    try:
        async def get_runtime_status():
            return await client.status()
        
        runtime_response = asyncio.run(get_runtime_status())
        if runtime_response.get('status') == 'running':
            typer.echo(f"  Runtime API: {typer.style('Accessible', fg=typer.colors.GREEN)}")
            typer.echo(f"  Runtime Status: {runtime_response.get('status').upper()}")
            typer.echo(f"  Runtime PID: {runtime_response.get('runtime_pid')}")
            typer.echo(f"  Llama.cpp Server: {runtime_response.get('llama_cpp_server').upper()}")
            typer.echo(f"  Model: {runtime_response.get('model').upper()}")
            if runtime_response.get('model_details'):
                typer.echo(f"    Path: {runtime_response['model_details'].get('path')}")
            if runtime_response.get('llama_cpp_api_url'):
                typer.echo(f"    Llama.cpp API: {runtime_response['llama_cpp_api_url']}")
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
    
    # Check for downloaded binaries and models (using ModelManager logic)
    typer.echo(typer.style("\nModel & Binary Availability (local):", fg=typer.colors.BLUE, bold=True))
    model_manager = ModelManager() # Instantiate to use its check logic

    def check_llama_cpp_binary():
        # This will simulate the logic in ModelManager for MVP
        bin_dir = Path(paths.get_bin_dir())
        dummy_binary_path = bin_dir / "llama_cpp_dummy_binary" # As created in ModelManager
        # In a real impl, ModelManager would return the actual binary path
        return dummy_binary_path.exists() and dummy_binary_path.is_file(), f"Llama.cpp binary not found at '{dummy_binary_path}'. Try 'imrabo start' to download."
    check("Llama.cpp binary", check_llama_cpp_binary)

    def check_model_files():
        selected_model_config = model_manager.get_preferred_model()
        if not selected_model_config:
            return False, "No preferred model could be determined based on system RAM and registry."
        
        model_variant = selected_model_config["variants"][0]
        model_filename = f"{selected_model_config['id']}-{model_variant['id']}.gguf"
        model_path = Path(paths.get_models_dir()) / model_filename
        
        return model_path.exists() and model_path.is_file(), f"Model file '{model_path}' not found. Try 'imrabo start' to download."
    check("Model file", check_model_files)

    typer.echo("\n--- Doctor Check Summary ---")
    if all_passed:
        typer.echo(typer.style("All checks PASSED!", fg=typer.colors.GREEN, bold=True))
        return typer.Exit(0)
    else:
        typer.echo(typer.style("Some checks FAILED. Please review the output above.", fg=typer.colors.RED, bold=True))
        return typer.Exit(1)

if __name__ == "__main__":
    typer.run(doctor)
