import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path

from imrabo.adapters.storage_fs import FileSystemArtifactResolver
from imrabo.internal import paths

console = Console()

def install():
    """
    Download and install a model from the registry.
    """
    # This wiring will eventually be handled by a central Kernel/DI container
    registry_path = Path(__file__).parent.parent.parent / "registry" / "models.json"
    models_dir = Path(paths.get_models_dir())
    resolver = FileSystemArtifactResolver(registry_path=registry_path, models_dir=models_dir)

    models = list(resolver._models.values())

    if not models:
        console.print("[red]No models found in the registry.[/red]")
        raise typer.Exit(1)

    # ------------------------------------------------------------------
    # Models Table
    # ------------------------------------------------------------------

    table = Table(title="Available Models")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Min RAM", justify="right", style="green")

    for model in models:
        table.add_row(
            model["id"],
            model.get("description", "No description"),
            f"{model.get('min_ram_gb', '?')} GB",
        )
    console.print(table)

    model_id = typer.prompt("Enter the ID of the model to install").strip()
    selected_model = resolver._models.get(model_id)
    if not selected_model:
        console.print(f"[red]Model '{model_id}' not found.[/red]")
        raise typer.Exit(1)

    variants = selected_model.get("variants", [])
    if not variants:
        console.print(f"[red]No variants found for model '{model_id}'.[/red]")
        raise typer.Exit(1)

    # ------------------------------------------------------------------
    # Variants Table
    # ------------------------------------------------------------------

    variant_table = Table(title=f"Available Variants for {model_id}")
    variant_table.add_column("ID", style="cyan", no_wrap=True)
    variant_table.add_column("Size", justify="right", style="green")
    variant_table.add_column("Notes")

    for v in variants:
        total_size_gb = sum(f.get('size_gb', 0) for f in v.get('files', []))
        variant_table.add_row(
            v["id"],
            f"{total_size_gb:.2f} GB",
            v.get("notes", ""),
        )
    console.print(variant_table)

    variant_id = typer.prompt("Enter the ID of the variant to install").strip()
    if not any(v["id"] == variant_id for v in variants):
        console.print(f"[red]Variant '{variant_id}' not found.[/red]")
        raise typer.Exit(1)

    console.print(f"\nInstalling model '{model_id}' with variant '{variant_id}'...\n")

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    try:
        # Construct the artifact reference string
        ref = f"model:{model_id}/variant:{variant_id}"
        handle = resolver.ensure_available(ref)
        
        if not handle.is_available:
            raise RuntimeError("Resolver failed to make artifact available.")

    except Exception as exc:
        console.print(f"[red]Installation failed:[/red] {exc}")
        raise typer.Exit(1)

    console.print(
        f"[green]Model '{model_id}' ({variant_id}) installed successfully.[/green]"
    )
    console.print(f"[dim]Model path:[/dim] {handle.location}")
