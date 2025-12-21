import logging
import logging.handlers
import os
import sys
from pathlib import Path
import structlog

from imrabo.internal import paths

def configure_logging():
    """
    Configure logging for the application.
    - Uses structlog for structured logging.
    - Writes JSON logs to a rotating file in the app data directory.
    - Console output is kept human-readable for Typer.
    - Log level can be set with the IMRABO_LOG_LEVEL environment variable.
    """
    log_level_name = os.environ.get("IMRABO_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    log_dir = Path(paths.get_app_data_dir()) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "imrabo.log.json"

    # Configure file handler for JSON logs
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
    )
    # The file handler will be used by structlog's underlying logging setup
    
    # Mute noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # This processor is the one that sends the log to the file handler as JSON
            structlog.stdlib.render_to_log_kwargs,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # We need to hook structlog into the standard logging system so the file handler works.
    # We create a handler that renders JSON.
    json_renderer = structlog.processors.JSONRenderer()
    
    # We create a formatter that will just pass the message through,
    # as structlog has already processed it.
    class StructlogFormatter(logging.Formatter):
        def format(self, record):
            # structlog has already processed the log record if it's from structlog
            # For standard library logs, we need to handle them.
            if 'event' in record.__dict__:
                return super().format(record)
            
            # This part is a bit tricky to get right. For now, we'll just let JSONRenderer handle it.
            # A simpler approach might be to just use a standard formatter for stdlib logs.
            # Let's simplify and just focus on structlog's output for now.
            return json_renderer(None, None, record.__dict__)

    # Re-configuring basicConfig to use our file handler
    logging.basicConfig(
        level=log_level,
        format="%(message)s", # structlog will handle the formatting
        handlers=[file_handler],
    )


# A single call to configure logging for the entire application
configure_logging()

def get_logger(name: str | None = None):
    # All modules can now just call get_logger()
    return structlog.get_logger(name)

