import typer
from imrabo.cli import core

def start():
    """
    Start the imrabo runtime daemon.
    """
    if core.is_runtime_active(core.RuntimeClient()):
        typer.echo("imrabo runtime is already running.")
        raise typer.Exit()

    typer.echo("Starting imrabo runtime...")
    success = core.start_runtime()
    
    if success:
        typer.echo("imrabo runtime started successfully.")
    else:
        typer.echo(typer.style("Error: Failed to start imrabo runtime.", fg=typer.colors.RED))
        raise typer.Exit(1)

