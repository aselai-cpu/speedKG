"""
Structured Logging Setup

Configures structlog for structured JSON logging with timestamps and context.
"""

import sys
import logging
from pathlib import Path
import structlog
from structlog.types import EventDict, WrappedLogger


def setup_logging(log_level: str = "INFO", logs_dir: Path | None = None) -> structlog.BoundLogger:
    """
    Configure structlog for structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        logs_dir: Directory to write log files (if None, logs to stdout only)

    Returns:
        Configured structlog logger
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level
    )

    # Processors for structlog
    processors = [
        # Add log level
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        # Format exceptions
        structlog.processors.format_exc_info,
        # Decode unicode
        structlog.processors.UnicodeDecoder(),
    ]

    # Add file handler if logs_dir specified
    if logs_dir:
        logs_dir.mkdir(exist_ok=True)
        log_file = logs_dir / "speedkg.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)

        # JSON formatter for file output
        json_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=processors
        )
        file_handler.setFormatter(json_formatter)

        # Add handler to root logger
        logging.root.addHandler(file_handler)

    # Configure structlog
    structlog.configure(
        processors=processors + [
            # Filter by log level
            structlog.stdlib.filter_by_level,
            # Render to console (dev-friendly format for stdout)
            structlog.dev.ConsoleRenderer() if sys.stdout.isatty() else structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger()
    logger.info("logging_configured", level=log_level, logs_dir=str(logs_dir) if logs_dir else None)

    return logger


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Bound logger
    """
    return structlog.get_logger(name)


# Context manager for logging contexts
class LoggingContext:
    """Context manager for adding contextual information to logs."""

    def __init__(self, **context):
        """
        Initialize with context key-value pairs.

        Args:
            **context: Key-value pairs to add to log context
        """
        self.context = context
        self.logger = structlog.get_logger()

    def __enter__(self):
        """Enter context."""
        self.logger = self.logger.bind(**self.context)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        # Unbind context
        self.logger = self.logger.unbind(*self.context.keys())
        return False


# Utility function for logging function execution
def log_execution(logger: structlog.BoundLogger):
    """
    Decorator to log function execution.

    Args:
        logger: Structlog logger instance
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(
                "function_start",
                function=func.__name__,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )

            try:
                result = func(*args, **kwargs)
                logger.debug(
                    "function_complete",
                    function=func.__name__
                )
                return result

            except Exception as e:
                logger.error(
                    "function_error",
                    function=func.__name__,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

        return wrapper
    return decorator


# Example usage
if __name__ == "__main__":
    # Setup logging
    logger = setup_logging(log_level="DEBUG", logs_dir=Path("logs"))

    # Basic logging
    logger.info("test_message", user="alice", action="login")
    logger.warning("test_warning", code=404, resource="/api/test")
    logger.error("test_error", error="Something went wrong")

    # Using context
    with LoggingContext(request_id="req-123", user="bob"):
        logger.info("processing_request", step="validation")
        logger.info("processing_request", step="execution")

    # Testing exception logging
    try:
        raise ValueError("Test exception")
    except Exception as e:
        logger.error("exception_caught", error=str(e), exc_info=True)

    logger.info("logging_demo_complete")
