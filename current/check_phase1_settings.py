from src.core.config import get_settings


def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    print("song_source:", settings.song_source)
    print("sqlite_db_path:", settings.sqlite_db_path)
    print("sqlite_max_size_bytes:", settings.sqlite_max_size_bytes)
    print("neverending_songs_source_name:", settings.neverending_songs_source_name)
    print("neverending_songs_station:", settings.neverending_songs_station)
    print("enable_mac_notifications:", settings.enable_mac_notifications)


if __name__ == "__main__":
    main()
