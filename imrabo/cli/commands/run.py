import typer
import asyncio

from imrabo.cli import core
from imrabo.cli.client import RuntimeClient
from imrabo.internal.logging import get_logger

logger = get_logger()

def run(prompt: str):
    """
    Run a prompt through the local AI model.
    """
    client = core.RuntimeClient()

    # Check if runtime is active, if not, try to start it
    if not core.is_runtime_active(client):
        typer.echo("imrabo runtime is not active. Attempting to start it...")
        if not core.start_runtime():
            typer.echo(typer.style("Error: Could not start imrabo runtime. Please run 'imrabo start' manually and check logs.", fg=typer.colors.RED))
            raise typer.Exit(1)
        typer.echo("Runtime started successfully.")

    typer.echo("Sending prompt to runtime...")
    
    async def stream_response():
        try:
            # Use a context manager to handle the async generator
            async for chunk in client.run_prompt(prompt):
                typer.echo(chunk, nl=False)
            typer.echo("") # Final newline
        except RuntimeError as e:
            typer.echo(f"\n{typer.style('Error from runtime:', fg=typer.colors.RED)} {e}", err=True)
            logger.error("Error while running prompt", exc_info=e)
            raise typer.Exit(1)
        except Exception as e:
            typer.echo(f"\n{typer.style('An unexpected error occurred:', fg=typer.colors.RED)} {e}", err=True)
            logger.error("Unexpected error while running prompt", exc_info=e)
            raise typer.Exit(1)

    asyncio.run(stream_response())

