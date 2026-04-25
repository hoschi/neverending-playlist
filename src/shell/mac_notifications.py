import json
import shutil
import subprocess
from datetime import UTC, datetime

from loguru import logger

from src.core.config import Settings


def notify_error_if_enabled(settings: Settings, message: str) -> None:
    """Send a macOS notification for errors when enabled in settings."""
    if not settings.enable_mac_notifications:
        return

    timestamp = datetime.now(UTC).isoformat()
    full_message = f"[{timestamp}] {message}"
    _send_macos_notification("Neverending Playlist", full_message)


def _send_macos_notification(title: str, message: str) -> None:
    script = (
        f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    )
    executable = shutil.which("osascript")
    if executable is None:
        logger.warning("osascript is not available on this system")
        return

    try:
        process = subprocess.run(
            [executable, "-e", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except FileNotFoundError:
        logger.warning("osascript is not available on this system")
        return
    except subprocess.TimeoutExpired:
        logger.warning("Timed out while sending macOS notification")
        return

    if process.returncode != 0:
        stderr = process.stderr.strip() or "unknown osascript error"
        logger.warning("Failed to send macOS notification: {error}", error=stderr)
