import pytest
from typer.testing import CliRunner
from pathlib import Path

from imrabo.cli.main import cli_app

runner = CliRunner()
GOLDEN_FILES_DIR = Path(__file__).parent / "golden_output"

# Ensure the golden files directory exists
GOLDEN_FILES_DIR.mkdir(exist_ok=True)

@pytest.mark.parametrize("command, golden_filename", [
    (["--help"], "cli_help.txt"),
    (["start", "--help"], "start_help.txt"),
    (["stop", "--help"], "stop_help.txt"),
    (["status", "--help"], "status_help.txt"),
    (["run", "--help"], "run_help.txt"),
    (["install", "--help"], "install_help.txt"),
    (["doctor", "--help"], "doctor_help.txt"),
    (["version", "--help"], "version_help.txt"),
])
def test_cli_help_output_stability(command, golden_filename):
    """
    Tests that the --help output for various commands remains stable
    against golden files.
    """
    golden_file_path = GOLDEN_FILES_DIR / golden_filename
    result = runner.invoke(cli_app, command)

    assert result.exit_code == 0, f"Command '{' '.join(command)}' failed with exit code {result.exit_code}. Output: {result.stdout + result.stderr}"

    # Generate golden file if it doesn't exist (for first run or update)
    if not golden_file_path.exists():
        golden_file_path.write_text(result.stdout)
        pytest.fail(f"Golden file '{golden_file_path}' created. Please inspect and commit it.")

    expected_output = golden_file_path.read_text()
    assert result.stdout == expected_output, f"Output for command '{' '.join(command)}' has changed.\n" \
                                             f"---
 Expected ---
{expected_output}\n" \
                                             f"---
 Actual ---
{result.stdout}\n" \
                                             f"If this change is intentional, update the golden file:\n" \
                                             f"cp {GOLDEN_FILES_path.resolve()} {golden_file_path.resolve()}"

@pytest.mark.parametrize("command, golden_filename, expected_exit_code", [
    # Placeholder for non-help commands, daemon mocking needed for stability
    # For instance, a 'version' command output will be stable.
    (["version"], "version_output.txt", 0),
])
def test_cli_command_output_stability(command, golden_filename, expected_exit_code):
    """
    Tests that the output for specific commands remains stable against golden files.
    Requires mocking for commands interacting with the daemon.
    """
    golden_file_path = GOLDEN_FILES_DIR / golden_filename
    result = runner.invoke(cli_app, command)

    assert result.exit_code == expected_exit_code, f"Command '{' '.join(command)}' failed with exit code {result.exit_code}. Output: {result.stdout + result.stderr}"

    if not golden_file_path.exists():
        golden_file_path.write_text(result.stdout)
        pytest.fail(f"Golden file '{golden_file_path}' created. Please inspect and commit it.")

    expected_output = golden_file_path.read_text()
    assert result.stdout == expected_output, f"Output for command '{' '.join(command)}' has changed.\n" \
                                             f"---
 Expected ---
{expected_output}\n" \
                                             f"---
 Actual ---
{result.stdout}\n" \
                                             f"If this change is intentional, update the golden file:\n" \
                                             f"cp {GOLDEN_FILES_DIR.resolve()} {golden_file_path.resolve()}"
