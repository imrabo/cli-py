import logging
import logging.handlers
import os
import sys
from pathlib import Path
import structlog

from imrabo.internal import paths

_LOGGING_CONFIGURED = False

def setup_logging(log_level_name: str = "INFO", log_file_path: Path = None, console_output: bool = False):
    """
    Configure logging for the application.
    - Uses structlog for structured logging.
    - Writes JSON logs to a rotating file in the app data directory if log_file_path is provided.
    - Can optionally send human-readable or structured logs to console.
    - Log level can be set with the IMRABO_LOG_LEVEL environment variable or function argument.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return # Prevent re-configuring logging

    # Determine log level
    effective_log_level_name = os.environ.get("IMRABO_LOG_LEVEL", log_level_name).upper()
    log_level = getattr(logging, effective_log_level_name, logging.INFO)

    handlers = []

    # File handler for JSON logs
    if log_file_path:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
        )
        # File handler will use a JSONRenderer
        file_handler.setFormatter(structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=False) if not log_file_path.name.endswith('.json') else structlog.processors.JSONRenderer(),
            foreign_pre_chain=[
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
            ]
        ))
        handlers.append(file_handler)

    # Console handler for human-readable output
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(),
            foreign_pre_chain=[
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
            ]
        ))
        handlers.append(console_handler)
    
    # If no handlers, create a NullHandler to prevent "No handlers could be found for logger" messages
    if not handlers:
        handlers.append(logging.NullHandler())

    # Mute noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter, # Key to integrate with stdlib handlers
    ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard Python logger with handlers
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
    )
    _LOGGING_CONFIGURED = True

def get_logger(name: str | None = None):
    # All modules can now just call get_logger()
    return structlog.get_logger(name)

# Default logging configuration for application startup
# This will be called once on import if not explicitly configured by an entry point.
# It ensures some logging is always set up.
if not _LOGGING_CONFIGURED:
    default_log_dir = Path(paths.get_app_data_dir()) / "logs"
    default_log_file = default_log_dir / "imrabo.log.json"
    setup_logging(log_file_path=default_log_file, console_output=True)

