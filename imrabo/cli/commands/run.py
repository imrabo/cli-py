import typer
import asyncio

from imrabo.cli.commands import start as start_command # Alias to avoid name conflict
from imrabo.cli.client import RuntimeClient
from imrabo.internal.logging import configure_logging

logger = configure_logging()

def run(prompt: str):
    """
    Run a prompt through the local AI model.
    """
    client = RuntimeClient()

    # Check if runtime is active, if not, try to start it
    async def check_and_start_runtime():
        try:
            health_status = await client.health()
            if health_status.get("status") == "ok":
                return True
        except Exception:
            pass # Runtime not active
        
        typer.echo("imrabo runtime is not active. Attempting to start it...")
        # Call the start command directly
        start_command.start()
        # After start, recheck health
        try:
            health_status = await client.health()
            return health_status.get("status") == "ok"
        except Exception:
            return False

    if not asyncio.run(check_and_start_runtime()):
        typer.echo("Error: Could not ensure imrabo runtime is active. Please run 'imrabo start' manually.")
        return typer.Exit(1)

    typer.echo(f"Sending prompt to runtime...")
    
    async def stream_response():
        try:
            async for chunk in client.run_prompt(prompt):
                typer.echo(chunk, nl=False) # nl=False to print chunks without newlines
            typer.echo("") # Add a final newline after streaming is done
        except RuntimeError as e:
            typer.echo(f"\nError from runtime: {e}", err=True)
            logger.error(f"Error while running prompt: {e}")
            return typer.Exit(1)
        except Exception as e:
            typer.echo(f"\nAn unexpected error occurred: {e}", err=True)
            logger.error(f"Unexpected error while running prompt: {e}")
            return typer.Exit(1)

    asyncio.run(stream_response())
    return typer.Exit(0)

if __name__ == "__main__":
    typer.run(run)
