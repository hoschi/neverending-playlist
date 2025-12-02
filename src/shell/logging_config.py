import sys

from loguru import logger

from src.core.config import get_settings


def setup_logging() -> None:  # pragma: no cover
    """Configures the Loguru logger based on application settings."""
    settings = get_settings()
    logger.remove()  # Remove default handler to reconfigure cleanly.

    # Determine log level - allow TRACE level for debugging
    log_level = settings.log_level.upper()
    if log_level == "TRACE":
        # For TRACE level, we need to enable it specifically in loguru
        import os

        # Set LOGURU_LEVEL environment variable for TRACE support
        os.environ["LOGURU_LEVEL"] = "TRACE"

    # Console logger with an informative format and colors
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Optional file logger
    if settings.log_to_file:
        logger.add(
            "logs/app.log",
            rotation="10 MB",  # Rotates the file when it reaches 10 MB
            retention="7 days",  # Keeps logs for 7 days
            level=log_level,
            enqueue=True,  # Makes logging process-safe
            backtrace=True,  # Shows the full stacktrace on errors
            diagnose=True,  # Adds useful debug information to exceptions
            format="{time} {level} {message}",
        )

    # TRACE-level specific console logger for WatchService debugging
    logger.add(
        sys.stderr,
        level="TRACE",
        format="<yellow>{time:HH:mm:ss.SSS}</yellow> | <level>{level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
        colorize=True,
        filter=lambda record: "WatchService" in record["name"]
        or "[Thread" in record["message"],
    )
