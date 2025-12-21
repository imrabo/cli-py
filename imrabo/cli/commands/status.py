import typer
import asyncio
from imrabo.cli.client import RuntimeClient
from imrabo.internal.logging import configure_logging

logger = configure_logging()

def status():
    """
    Get the status of the imrabo runtime.
    """
    typer.echo("Checking imrabo runtime status...")
    client = RuntimeClient()
    try:
        async def get_runtime_status():
            return await client.status()
        
        runtime_status = asyncio.run(get_runtime_status())
        
        typer.echo(f"\nRuntime Status: {runtime_status.get('status', 'unknown').upper()}")
        typer.echo(f"  PID: {runtime_status.get('runtime_pid', 'N/A')}")
        typer.echo(f"  Model Status: {runtime_status.get('model', 'N/A').upper()}")
        if runtime_status.get('model_details'):
            typer.echo(f"    Model Name: {runtime_status['model_details'].get('name', 'N/A')}")
            typer.echo(f"    Model Path: {runtime_status['model_details'].get('path', 'N/A')}")
        typer.echo(f"  Llama.cpp Server: {runtime_status.get('llama_cpp_server', 'N/A').upper()}")
        typer.echo(f"  Llama.cpp API URL: {runtime_status.get('llama_cpp_api_url', 'N/A')}")

    except Exception as e:
        typer.echo(f"Could not connect to imrabo runtime. Is it running? Error: {e}")
        logger.error(f"Error checking runtime status: {e}")
        return typer.Exit(1)

if __name__ == "__main__":
    typer.run(status)
