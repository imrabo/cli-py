import typer

from imrabo.cli.commands import (
    start,
    stop,
    restart, # Added restart
    status,
    doctor,
    run,
    version,
)

app = typer.Typer(
    name="imrabo",
    help="A local-first AI CLI runtime.",
    no_args_is_help=True
)

app.command("start")(start.start)
app.command("stop")(stop.stop)
app.command("restart")(restart.restart) # Registered restart
app.command("status")(status.status)
app.command("doctor")(doctor.doctor)
app.command("run")(run.run)
app.command("version")(version.version)

if __name__ == "__main__":
    app()
