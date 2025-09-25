from typer.testing import CliRunner

from src.shell.cli import app

runner = CliRunner()


def test_transform_command_success() -> None:
    """
    Tests the 'transform' CLI command with a sample string.
    """
    result = runner.invoke(app, ["transform", "error"])
    assert result.exit_code == 0
    assert "Error:" in result.stdout


def test_transform_command_error() -> None:
    """
    Tests the 'transform' CLI command with a sample string.
    """
    result = runner.invoke(app, ["transform", "  Some Text  "])
    assert result.exit_code == 0
    assert "Success:" in result.stdout
    assert "transformed: some text" in result.stdout


def test_get_user_command_success() -> None:
    """
    Tests the 'get-user' CLI command for a user that exists.
    """
    result = runner.invoke(app, ["get-user", "1"])
    assert result.exit_code == 0
    assert "Alice" in result.stdout
    assert "30" in result.stdout


def test_get_user_command_not_found() -> None:
    """
    Tests the 'get-user' CLI command for a user that does not exist.
    """
    result = runner.invoke(app, ["get-user", "999"])
    assert result.exit_code == 0
    assert "Error:" in result.stdout
    assert "No user found with id: 999" in result.stdout
