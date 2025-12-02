import sys

from loguru import logger

from src.core.config import get_settings


def setup_logging() -> None:  # pragma: no cover
    """Configures the Loguru logger based on application settings."""
    settings = get_settings()
    logger.remove()  # Remove default handler to reconfigure cleanly.

    # Console logger with an informative format and colors
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Optional file logger
    if settings.log_to_file:
        logger.add(
            "logs/app.log",
            rotation="10 MB",  # Rotates the file when it reaches 10 MB
            retention="7 days",  # Keeps logs for 7 days
            level=settings.log_level.upper(),
            enqueue=True,  # Makes logging process-safe
            backtrace=True,  # Shows the full stacktrace on errors
            diagnose=True,  # Adds useful debug information to exceptions
            format="{time} {level} {message}",
        )
