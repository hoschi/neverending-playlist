import typer
from loguru import logger

from src.shell.logging_config import setup_logging

app: typer.Typer = typer.Typer()


@app.command()
def hello(name: str) -> None:
    """A simple CLI command that prints a greeting."""
    logger.info(f"CLI command 'hello' called with name: '{name}'")
    print(f"Hello, {name}!")


def main() -> None:  # pragma: no cover
    """Main function to run the Typer CLI application."""
    setup_logging()
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
