import asyncio
import typer

from imrabo.cli import core
from imrabo.cli.client import RuntimeClient

def run():
    client = RuntimeClient()

    if not core.is_runtime_active(client):
        typer.echo("Starting runtime...")
        if not core.start_runtime():
            typer.echo("Failed to start runtime")
            raise typer.Exit(1)

    typer.echo("\nimrabo chat started. Type /exit to quit.\n")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        while True:
            user_input = input("You: ").strip()

            if user_input.lower() in {"/exit", "exit", "quit"}:
                print("Goodbye.")
                break

            print("Assistant: ", end="", flush=True)

            async def run_once():
                async for delta in client.run_prompt(user_input):
                    print(delta, end="", flush=True)

            loop.run_until_complete(run_once())
            print()

    finally:
        loop.close()
