from src.core.config import get_settings
from src.shell.mac_notifications import notify_error_if_enabled


def main() -> None:
    settings = get_settings()
    print(f"enable_mac_notifications={settings.enable_mac_notifications}")
    notify_error_if_enabled(
        settings,
        "Phase 5 test notification (forced error simulation)",
    )
    print("Notification call executed (see macOS Notification Center if enabled).")


if __name__ == "__main__":
    main()
