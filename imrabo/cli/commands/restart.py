import typer
import time

from imrabo.cli.commands import stop, start

def restart():
    """
    Restart the imrabo runtime.
    """
    typer.echo("Restarting imrabo runtime...")
    stop.stop()
    time.sleep(2) # Give it a moment to fully shut down
    start.start()
    typer.echo("imrabo runtime restarted.")

if __name__ == "__main__":
    typer.run(restart)
