import pytest
from typer.testing import CliRunner

from imrabo.cli.main import cli_app

runner = CliRunner()

def test_cli_app_exists():
    """Verify that the CLI app instance is available."""
    assert cli_app is not None

# --- Valid Commands ---
@pytest.mark.parametrize("command, expected_output_substring", [
    (["--help"], "Usage: main"),
    (["start", "--help"], "Usage: main start"),
    (["stop", "--help"], "Usage: main stop"),
    (["status", "--help"], "Usage: main status"),
    (["run", "--help"], "Usage: main run"),
    (["install", "--help"], "Usage: main install"),
    (["doctor", "--help"], "Usage: main doctor"),
    (["version", "--help"], "Usage: main version"),
])
def test_valid_commands_help_output(command, expected_output_substring):
    """Test that valid commands and their --help flags work and produce expected output."""
    result = runner.invoke(cli_app, command)
    assert result.exit_code == 0
    assert expected_output_substring in result.stdout

# --- Invalid Commands ---
@pytest.mark.parametrize("command, expected_error_substring", [
    (["nonexistent-command"], "Error: No such command 'nonexistent-command'"),
    (["start", "extra-arg"], "Error: Got unexpected extra argument"),
    (["--invalid-global-flag"], "Error: Unknown option '--invalid-global-flag'"),
])
def test_invalid_commands_fail_loudly(command, expected_error_substring):
    """Test that invalid commands or arguments fail with non-zero exit code and error message."""
    result = runner.invoke(cli_app, command)
    assert result.exit_code != 0
    assert expected_error_substring in result.stderr

# --- Flag Stability (conceptual, actual values tested in backward-compat) ---
@pytest.mark.parametrize("command_with_flag, expected_exit_code", [
    (["start"], 0), # This will mock starting, so exit_code 0 is expected
    (["stop"], 0),
    (["doctor"], 0), # Will likely fail without daemon but should not be grammar error
])
@pytest.mark.skip(reason="Requires daemon mocking to pass reliably")
def test_command_exit_codes_stability(command_with_flag, expected_exit_code):
    """Test that basic commands produce expected exit codes (assuming successful execution setup)."""
    result = runner.invoke(cli_app, command_with_flag)
    assert result.exit_code == expected_exit_code

# Test for specific argument parsing (e.g., run command prompt)
def test_run_command_requires_prompt():
    """Test that 'run' command without a prompt argument fails."""
    # The 'run' command expects a prompt as an argument.
    # Its current implementation does not directly take a positional argument,
    # but relies on interactive input. This test might need adjustment
    # once 'run' is fully integrated with kernel for non-interactive mode.
    result = runner.invoke(cli_app, ["run"])
    assert result.exit_code != 0
    # The exact error depends on 'run' command's implementation detail
    # For now, it will attempt to start chat, and then fail on input,
    # or if we change 'run' to take a prompt as an argument.
    # For now, we test the --help output above. More direct tests will come later.
    assert "Type /exit to quit" in result.stdout # It enters interactive mode
    # This test currently reflects the interactive nature, which will change.
    # Once 'run' takes --prompt or a positional, this test will change.
