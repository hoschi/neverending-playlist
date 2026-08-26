import sqlite3
import subprocess
from unittest.mock import patch

from returns.pipeline import is_successful

from src.core.models import NeverendingSongsImportStatus
from src.core.sqlite_schema import IMPORT_RUNS_TABLE, SQLITE_SCHEMA_STATEMENTS
from src.shell.neverending_songs import (
    FetchedPayload,
    NeverendingSongsEmptyPayloadError,
    _ensure_jq_available,
    _map_payload_with_jq,
    _safe_url_for_logging,
    _summarize_payload_for_log,
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


def test_payload_summary_exposes_null_result_shape() -> None:
    summary = _summarize_payload_for_log('{"result": null}')

    assert "json.object keys=[result]" in summary
    assert "result=null" in summary


def test_safe_url_for_logging_redacts_sensitive_query_values() -> None:
    safe_url = _safe_url_for_logging(
        "https://example.com/source?station=110&api_key=secret&token=abc"
    )

    assert "station=110" in safe_url
    assert "api_key=%2A%2A%2A" in safe_url
    assert "token=%2A%2A%2A" in safe_url
    assert "secret" not in safe_url
    assert "abc" not in safe_url


def test_map_payload_without_entry_raises_clear_error() -> None:
    payload = '{\n                    "result": {\n                    "found": "0"}}'

    try:
        _map_payload_with_jq(
            payload,
            "iris-bob.loverad.io",
            "2026-08-25T07:00:00.000+02:00",
            "2026-08-25T22:00:00.000+02:00",
            "https://iris-bob.loverad.io/search.json",
        )
    except NeverendingSongsEmptyPayloadError as error:
        message = str(error)
        assert "no entries" in message
        assert "found=0" in message
        assert "iris-bob.loverad.io" in message
        assert "Cannot iterate over null" not in message
        assert "jq mapping failed" not in message
    else:
        raise AssertionError(
            "Expected NeverendingSongsEmptyPayloadError when payload has no entry"
        )


def test_import_without_entry_returns_failure(tmp_path) -> None:
    sqlite_db_path = tmp_path / "neverending_songs.db"
    empty_payload = FetchedPayload(
        text='{"result": {"found": "0"}}',
        status_code=200,
        content_type="application/json",
        byte_count=26,
    )

    with patch(
        "src.shell.neverending_songs._fetch_payload", return_value=empty_payload
    ):
        result = run_neverending_songs_import(
            source_urls=["https://iris-bob.loverad.io/search.json?station=110"],
            sqlite_db_path=str(sqlite_db_path),
            sqlite_max_size_bytes=10_000_000,
        )

    assert not is_successful(result)
    error = result.failure()
    assert isinstance(error, NeverendingSongsEmptyPayloadError)
    assert "no entries" in str(error)

    connection = sqlite3.connect(sqlite_db_path)
    try:
        row = connection.execute(
            f"""
            SELECT status, details
            FROM {IMPORT_RUNS_TABLE}
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row[0] == NeverendingSongsImportStatus.FAILED.value
    assert "no entries" in str(row[1])


def test_jq_mapping_error_includes_source_context_and_payload_shape() -> None:
    failed_process = subprocess.CompletedProcess(
        args=["jq"],
        returncode=5,
        stdout="",
        stderr="jq: error (at <stdin>:2): Cannot iterate over null (null)",
    )

    with (
        patch("src.shell.neverending_songs._ensure_jq_available", return_value="jq"),
        patch(
            "src.shell.neverending_songs.subprocess.run", return_value=failed_process
        ),
    ):
        try:
            _map_payload_with_jq(
                '{"result": null}',
                "example.com",
                "2026-06-06T22:40:00+00:00",
                "2026-06-06T23:00:00+00:00",
                "https://example.com/source?api_key=***",
            )
        except RuntimeError as error:
            message = str(error)
            assert "source=example.com" in message
            assert "result=null" in message
            assert "Cannot iterate over null" in message
            assert "api_key=***" in message
        else:
            raise AssertionError("Expected RuntimeError when jq mapping fails")
