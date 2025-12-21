import typer
import importlib.metadata
from imrabo.internal.logging import configure_logging

logger = configure_logging()

def version():
    """
    Show the imrabo version.
    """
    try:
        # Read version from pyproject.toml via installed package metadata
        # This will only work correctly after the package is installed
        package_version = importlib.metadata.version("imrabo")
        typer.echo(f"imrabo version: {package_version}")
    except importlib.metadata.PackageNotFoundError:
        typer.echo("imrabo is not installed or version metadata not found.")
        typer.echo("Please install the package first (e.g., pip install . or pip install -e .)")
        logger.warning("imrabo package version not found.")
        return typer.Exit(1)

if __name__ == "__main__":
    typer.run(version)
