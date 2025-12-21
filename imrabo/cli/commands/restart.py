import typer
import time
from imrabo.cli import core

def restart():
    """
    Restart the imrabo runtime daemon.
    """
    typer.echo("Restarting imrabo runtime...")
    
    typer.echo("--> Stopping runtime...")
    if not core.stop_runtime():
        typer.echo(typer.style("Failed to stop runtime. Please check logs or stop it manually.", fg=typer.colors.RED))
        raise typer.Exit(1)
    
    typer.echo("Runtime stopped. Waiting a moment before starting...")
    time.sleep(2)

    typer.echo("--> Starting runtime...")
    if not core.start_runtime():
        typer.echo(typer.style("Failed to start runtime. Please check logs.", fg=typer.colors.RED))
        raise typer.Exit(1)

    typer.echo("imrabo runtime restarted successfully.")

