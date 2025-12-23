import pytest
import logging
import json
from pathlib import Path
import os
import structlog

# Import the refactored logging setup
from imrabo.internal.logging import setup_logging, get_logger

# --- Fixtures ---

@pytest.fixture(autouse=True)
def reset_logging():
    """Ensure logging state is clean for each test."""
    # Reset structlog and logging handlers
    structlog.configure(processors=[])
    logging.root.handlers = []
    logging.root.setLevel(logging.NOTSET)
    # Clear any global config flags in logging module
    if hasattr(structlog.stdlib, '_LOGGER_FACTORY_CONFIGURED'):
        delattr(structlog.stdlib, '_LOGGER_FACTORY_CONFIGURED')
    if hasattr(structlog, '_configured'):
        delattr(structlog, '_configured')
    if hasattr(os.environ, 'IMRABO_LOG_LEVEL'):
        del os.environ['IMRABO_LOG_LEVEL']
    
    # Patch the global _LOGGING_CONFIGURED flag in our module
    with patch('imrabo.internal.logging._LOGGING_CONFIGURED', False) as patched_flag:
        yield
        # After test, clean up any file handlers that might have been created
        for handler in logging.root.handlers[:]:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                handler.close()
            logging.root.removeHandler(handler)


@pytest.fixture
def caplog_json(caplog):
    """
    A fixture that captures log output as JSON for verification.
    It configures logging to write to a temporary file in JSON format.
    """
    # Override default setup to ensure JSON output and capture to a file
    def _setup_json_logging(log_level="DEBUG"):
        # We need a unique file per test to avoid conflicts
        log_file = Path(caplog.handler.baseFilename).parent / "test_log.json"
        setup_logging(log_level_name=log_level, log_file_path=log_file, console_output=False)
        return log_file

    yield _setup_json_logging

    # No specific teardown, reset_logging handles it


# --- Tests ---

def test_logging_is_structured_json(caplog_json):
    """Verify that logs are emitted in a structured JSON format to file."""
    log_file = caplog_json("INFO")
    logger = get_logger("test.module")

    logger.info("Test event", key="value", another_key=123)

    with open(log_file, 'r') as f:
        log_entry = json.loads(f.readline())

    assert "event" in log_entry
    assert log_entry["event"] == "Test event"
    assert "key" in log_entry and log_entry["key"] == "value"
    assert "another_key" in log_entry and log_entry["another_key"] == 123
    assert "timestamp" in log_entry
    assert "level" in log_entry and log_entry["level"] == "info"
    assert "logger" in log_entry and log_entry["logger"] == "test.module"


def test_logging_contains_required_fields(caplog_json):
    """Ensure every log entry contains essential fields."""
    log_file = caplog_json("ERROR")
    logger = get_logger("required.fields")

    logger.error("Critical error occurred", error_code=500, user_id="abc")

    with open(log_file, 'r') as f:
        log_entry = json.loads(f.readline())

    assert "timestamp" in log_entry
    assert "level" in log_entry
    assert "logger" in log_entry
    assert "event" in log_entry
    assert log_entry["level"] == "error"
    assert log_entry["event"] == "Critical error occurred"
    assert "error_code" in log_entry and log_entry["error_code"] == 500


def test_logging_avoids_sensitive_data(caplog_json):
    """Verify that sensitive data (e.g., auth tokens) is not logged."""
    log_file = caplog_json("INFO")
    logger = get_logger("security.module")

    sensitive_token = "Bearer_sk-abcdef1234567890"
    user_password = "mysecretpassword"
    
    # Log something that might inadvertently contain sensitive info
    logger.info("User login attempt", username="testuser", auth_header=sensitive_token, password=user_password)

    with open(log_file, 'r') as f:
        log_entry = json.loads(f.readline())
    
    # Assert sensitive data is NOT present in the logged event data
    assert sensitive_token not in json.dumps(log_entry)
    assert user_password not in json.dumps(log_entry)
    
    # This test is somewhat weak. Proper sensitive data redaction would require
    # a custom structlog processor. For now, it checks if it's explicitly passed.
    # In a real system, the input to the logger should be sanitized *before* logging.

def test_logging_level_filtering(caplog_json):
    """Test that logs are filtered by level correctly."""
    log_file = caplog_json("INFO") # Set global level to INFO
    logger = get_logger("filter.test")

    logger.debug("Debug message - should not appear")
    logger.info("Info message - should appear")
    logger.warning("Warning message - should appear")

    with open(log_file, 'r') as f:
        log_lines = f.readlines()
    
    logged_events = [json.loads(line)["event"] for line in log_lines]

    assert "Debug message - should not appear" not in logged_events
    assert "Info message - should appear" in logged_events
    assert "Warning message - should appear" in logged_events

def test_logging_console_output_control(capsys, reset_logging):
    """Test that console output can be controlled."""
    # Configure logging to ONLY go to console, no file
    setup_logging(log_level_name="INFO", log_file_path=None, console_output=True)
    logger = get_logger("console.test")

    logger.info("Hello console!")
    
    captured = capsys.readouterr()
    assert "Hello console!" in captured.out
    assert "INFO" in captured.out # Default ConsoleRenderer includes level

def test_logging_no_handlers_configured_sends_to_null(capsys, reset_logging):
    """Test that if no handlers are specified, logging goes to NullHandler (no output)."""
    # Configure logging with no file and no console output
    setup_logging(log_level_name="INFO", log_file_path=None, console_output=False)
    logger = get_logger("null.test")

    logger.info("This should not be seen.")
    
    captured = capsys.readouterr()
    assert "This should not be seen." not in captured.out
    # Also verify no file was created implicitly, though setup_logging does that already
