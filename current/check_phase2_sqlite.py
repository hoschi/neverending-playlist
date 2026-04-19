import json
import sqlite3

from src.core.config import get_settings
from src.core.sqlite_schema import IMPORT_RUNS_TABLE, SONG_REQUESTS_TABLE


def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    connection = sqlite3.connect(settings.sqlite_db_path)
    try:
        cursor = connection.cursor()
        songs_count = cursor.execute(
            f"SELECT COUNT(*) FROM {SONG_REQUESTS_TABLE}"
        ).fetchone()[0]
        runs_count = cursor.execute(
            f"SELECT COUNT(*) FROM {IMPORT_RUNS_TABLE}"
        ).fetchone()[0]
        latest_song = cursor.execute(
            f"SELECT artist, song, airtime, source FROM {SONG_REQUESTS_TABLE} ORDER BY id DESC LIMIT 1"
        ).fetchone()
        latest_run = cursor.execute(
            f"SELECT run_at, status, imported_count, source_count FROM {IMPORT_RUNS_TABLE} ORDER BY id DESC LIMIT 1"
        ).fetchone()

        print(
            json.dumps(
                {
                    "sqlite_db_path": settings.sqlite_db_path,
                    "song_rows": songs_count,
                    "run_rows": runs_count,
                    "latest_song": latest_song,
                    "latest_run": latest_run,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
