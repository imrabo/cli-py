import typer
import asyncio
import json
from imrabo.cli.client import RuntimeClient
from imrabo.internal.logging import get_logger

logger = get_logger(__name__)

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
        
        typer.echo("\n--- IMRABO Runtime Status ---")
        typer.echo(json.dumps(runtime_status, indent=2))
        typer.echo("----------------------------")

    except Exception as e:
        typer.echo(f"Could not connect to imrabo runtime. Is it running? Error: {e}")
        logger.error(f"Error checking runtime status: {e}")
        return typer.Exit(1)

if __name__ == "__main__":
    typer.run(status)
