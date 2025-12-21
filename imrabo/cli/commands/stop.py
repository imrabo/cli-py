import typer
from imrabo.cli import core

def stop():
    """
    Stop the imrabo runtime daemon.
    """
    typer.echo("Stopping imrabo runtime...")
    success = core.stop_runtime()

    if success:
        typer.echo("imrabo runtime stopped successfully.")
    else:
        typer.echo(typer.style("Error: Failed to stop imrabo runtime.", fg=typer.colors.RED))
        raise typer.Exit(1)

