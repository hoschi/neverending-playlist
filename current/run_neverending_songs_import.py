import json
import sys

from returns.pipeline import is_successful

from src.core.config import get_settings
from src.shell.neverending_songs import run_neverending_songs_import


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()

    result = run_neverending_songs_import(
        source_urls=settings.song_source_rest_urls,
        sqlite_db_path=settings.sqlite_db_path,
        sqlite_max_size_bytes=settings.sqlite_max_size_bytes,
    )

    if not is_successful(result):
        print(
            json.dumps({"status": "FAILED", "error": str(result.failure())}, indent=2)
        )
        return 1

    run = result.unwrap()
    print(
        json.dumps(
            {
                "status": run.status.value,
                "imported_count": run.imported_count,
                "source_count": run.source_count,
                "details": run.details,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
