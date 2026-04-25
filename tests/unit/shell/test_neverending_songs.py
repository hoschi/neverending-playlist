import sqlite3
from unittest.mock import patch

from returns.pipeline import is_successful

from src.core.models import NeverendingSongsImportStatus
from src.core.sqlite_schema import IMPORT_RUNS_TABLE, SQLITE_SCHEMA_STATEMENTS
from src.shell.neverending_songs import (
    _ensure_jq_available,
    run_neverending_songs_import,
)


def test_run_neverending_songs_import_persists_skipped_max_size_run(tmp_path) -> None:
    sqlite_db_path = tmp_path / "neverending_songs.db"

    connection = sqlite3.connect(sqlite_db_path)
    try:
        cursor = connection.cursor()
        for statement in SQLITE_SCHEMA_STATEMENTS:
            cursor.execute(statement)
        connection.commit()
    finally:
        connection.close()

    result = run_neverending_songs_import(
        source_urls=["https://example.com/source.json?station=110"],
        sqlite_db_path=str(sqlite_db_path),
        sqlite_max_size_bytes=1,
    )

    assert is_successful(result)
    run_summary = result.unwrap()
    assert run_summary.status == NeverendingSongsImportStatus.SKIPPED_MAX_DB_SIZE

    connection = sqlite3.connect(sqlite_db_path)
    try:
        row = connection.execute(
            f"""
            SELECT status, imported_count, source_count, details
            FROM {IMPORT_RUNS_TABLE}
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row[0] == NeverendingSongsImportStatus.SKIPPED_MAX_DB_SIZE.value
    assert row[1] == 0
    assert row[2] == 1
    assert "SQLite file size limit exceeded" in str(row[3])


def test_ensure_jq_available_raises_clear_error_when_binary_missing() -> None:
    with patch("src.shell.neverending_songs.shutil.which", return_value=None):
        try:
            _ensure_jq_available()
        except RuntimeError as error:
            message = str(error)
            assert "jq is required" in message
            assert "brew install jq" in message
            assert "apt install jq" in message
        else:
            raise AssertionError("Expected RuntimeError when jq is unavailable")
