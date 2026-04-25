import json
import os
import sqlite3
import subprocess
from datetime import UTC, datetime
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from loguru import logger
from returns.pipeline import is_successful
from returns.result import Failure, Result, Success

from src.core.models import (
    NeverendingSongsImportRun,
    NeverendingSongsImportStatus,
    NeverendingSongsMappedRecord,
)
from src.core.services.neverending_songs_service import (
    build_source_url_with_window,
    build_yesterday_utc_window_iso,
    resolve_source_window,
    source_from_url,
)
from src.core.sqlite_schema import (
    IMPORT_RUNS_TABLE,
    SONG_REQUESTS_TABLE,
    SQLITE_SCHEMA_STATEMENTS,
)

JQ_MAPPING_EXPRESSION = (
    ".result.entry[] | {artist: .song.entry[0].artist.entry[0].name, "
    "song: .song.entry[0].title, airtime: .airtime, source: $source}"
)


def run_neverending_songs_import(
    source_urls: list[str],
    sqlite_db_path: str,
    sqlite_max_size_bytes: int,
    window_minutes: int = 20,
) -> Result[NeverendingSongsImportRun, Exception]:
    """Imports songs from configured REST sources into SQLite."""
    if not source_urls:
        return Failure(ValueError("No source URLs configured"))

    size_guard_result = _guard_sqlite_file_size(sqlite_db_path, sqlite_max_size_bytes)
    if not is_successful(size_guard_result):
        details = str(size_guard_result.failure())
        try:
            _write_import_run(
                sqlite_db_path=sqlite_db_path,
                status=NeverendingSongsImportStatus.SKIPPED_MAX_DB_SIZE,
                imported_count=0,
                source_count=len(source_urls),
                details=details,
            )
        except Exception as run_write_error:
            logger.warning(
                "Failed to persist SKIPPED_MAX_DB_SIZE import run: {error}",
                error=run_write_error,
            )

        return Success(
            NeverendingSongsImportRun(
                status=NeverendingSongsImportStatus.SKIPPED_MAX_DB_SIZE,
                imported_count=0,
                source_count=len(source_urls),
                details=details,
            )
        )

    try:
        start_iso, end_iso = build_yesterday_utc_window_iso(
            window_end=datetime.now(UTC),
            window_minutes=window_minutes,
        )
        mapped_records: list[NeverendingSongsMappedRecord] = []
        resolved_windows: list[str] = []

        for source_url in source_urls:
            source_name = source_from_url(source_url)
            source_start_iso, source_end_iso = resolve_source_window(
                source_url,
                fallback_start_iso=start_iso,
                fallback_end_iso=end_iso,
                now_local=datetime.now().astimezone(),
            )
            resolved_url = _resolve_source_url(
                source_url,
                source_start_iso,
                source_end_iso,
            )
            resolved_windows.append(
                f"{source_name}:{source_start_iso}->{source_end_iso}"
            )
            payload = _fetch_payload(resolved_url)
            mapped_records.extend(_map_payload_with_jq(payload, source_name))

        imported_count = _write_records_to_sqlite(sqlite_db_path, mapped_records)
        run_details = ";".join(resolved_windows)
        _write_import_run(
            sqlite_db_path=sqlite_db_path,
            status=NeverendingSongsImportStatus.SUCCESS,
            imported_count=imported_count,
            source_count=len(source_urls),
            details=run_details,
        )

        logger.info(
            "NeverendingSongs import finished: imported={imported_count}, sources={source_count}",
            imported_count=imported_count,
            source_count=len(source_urls),
        )

        return Success(
            NeverendingSongsImportRun(
                status=NeverendingSongsImportStatus.SUCCESS,
                imported_count=imported_count,
                source_count=len(source_urls),
                details=run_details,
            )
        )
    except Exception as error:
        logger.error("NeverendingSongs import failed: {error}", error=error)
        try:
            _write_import_run(
                sqlite_db_path=sqlite_db_path,
                status=NeverendingSongsImportStatus.FAILED,
                imported_count=0,
                source_count=len(source_urls),
                details=str(error),
            )
        except Exception as run_write_error:
            logger.warning(
                "Failed to persist FAILED import run: {error}",
                error=run_write_error,
            )
        return Failure(error)


def _guard_sqlite_file_size(
    sqlite_db_path: str,
    sqlite_max_size_bytes: int,
) -> Result[None, Exception]:
    if sqlite_max_size_bytes <= 0:
        return Failure(ValueError("sqlite_max_size_bytes must be greater than 0"))

    if not os.path.exists(sqlite_db_path):
        return Success(None)

    file_size = os.path.getsize(sqlite_db_path)
    if file_size > sqlite_max_size_bytes:
        return Failure(
            RuntimeError(
                "SQLite file size limit exceeded: "
                f"{file_size} > {sqlite_max_size_bytes} bytes"
            )
        )

    return Success(None)


def _resolve_source_url(source_url: str, start_iso: str, end_iso: str) -> str:
    return build_source_url_with_window(source_url, start_iso, end_iso)


def _fetch_payload(url: str) -> str:
    try:
        with urlopen(url, timeout=30) as response:  # noqa: S310
            data = response.read()
        return cast(bytes, data).decode("utf-8")
    except HTTPError as error:
        raise RuntimeError(f"HTTP error for source {url}: {error.code}") from error
    except URLError as error:
        raise RuntimeError(f"URL error for source {url}: {error.reason}") from error


def _map_payload_with_jq(
    payload: str, source_name: str
) -> list[NeverendingSongsMappedRecord]:
    process = subprocess.run(
        [
            "jq",
            "-c",
            "--arg",
            "source",
            source_name,
            JQ_MAPPING_EXPRESSION,
        ],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )

    if process.returncode != 0:
        stderr = process.stderr.strip() or "unknown jq error"
        raise RuntimeError(f"jq mapping failed: {stderr}")

    records: list[NeverendingSongsMappedRecord] = []
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    for line in lines:
        row = json.loads(line)
        records.append(NeverendingSongsMappedRecord.model_validate(row))

    return records


def _ensure_sqlite_schema(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    for statement in SQLITE_SCHEMA_STATEMENTS:
        cursor.execute(statement)
    connection.commit()


def _write_records_to_sqlite(
    sqlite_db_path: str,
    mapped_records: list[NeverendingSongsMappedRecord],
) -> int:
    connection = sqlite3.connect(sqlite_db_path)
    try:
        _ensure_sqlite_schema(connection)
        cursor = connection.cursor()
        before_changes = connection.total_changes

        for record in mapped_records:
            cursor.execute(
                f"""
                INSERT OR IGNORE INTO {SONG_REQUESTS_TABLE}
                (artist, song, status, requested_by, airtime, source, external_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artist,
                    record.song,
                    record.status.value if record.status else None,
                    record.requested_by,
                    record.airtime,
                    record.source,
                    None,
                ),
            )

        connection.commit()
        return connection.total_changes - before_changes
    finally:
        connection.close()


def _write_import_run(
    sqlite_db_path: str,
    status: NeverendingSongsImportStatus,
    imported_count: int,
    source_count: int,
    details: str,
) -> None:
    connection = sqlite3.connect(sqlite_db_path)
    try:
        _ensure_sqlite_schema(connection)
        cursor = connection.cursor()
        cursor.execute(
            f"""
            INSERT INTO {IMPORT_RUNS_TABLE}
            (run_at, status, imported_count, source_count, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).isoformat(),
                status.value,
                imported_count,
                source_count,
                details,
            ),
        )
        connection.commit()
    finally:
        connection.close()
