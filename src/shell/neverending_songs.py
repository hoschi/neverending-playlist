import json
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
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
PAYLOAD_PREVIEW_CHARS = 500
SUMMARY_ITEM_LIMIT = 8
SENSITIVE_QUERY_MARKERS = ("key", "token", "secret", "password", "auth")


@dataclass(frozen=True)
class FetchedPayload:
    """Payload plus small response metadata for import diagnostics."""

    text: str
    status_code: int | None
    content_type: str | None
    byte_count: int


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
            safe_resolved_url = _safe_url_for_logging(resolved_url)
            logger.info(
                "NeverendingSongs source fetch started: "
                "source={source}, start={start}, end={end}, url={url}",
                source=source_name,
                start=source_start_iso,
                end=source_end_iso,
                url=safe_resolved_url,
            )

            try:
                payload = _fetch_payload(resolved_url)
                logger.info(
                    "NeverendingSongs source fetch finished: "
                    "source={source}, http_status={status}, content_type={content_type}, "
                    "bytes={bytes}, payload={payload_summary}",
                    source=source_name,
                    status=payload.status_code,
                    content_type=payload.content_type,
                    bytes=payload.byte_count,
                    payload_summary=_summarize_payload_for_log(payload.text),
                )
                source_records = _map_payload_with_jq(
                    payload.text,
                    source_name,
                    source_start_iso,
                    source_end_iso,
                    safe_resolved_url,
                )
            except Exception as source_error:
                raise RuntimeError(
                    "source import failed: "
                    f"source={source_name}, start={source_start_iso}, "
                    f"end={source_end_iso}, url={safe_resolved_url}, "
                    f"error={source_error}"
                ) from source_error

            logger.info(
                "NeverendingSongs source mapped: source={source}, records={records}",
                source=source_name,
                records=len(source_records),
            )
            mapped_records.extend(source_records)

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
        logger.exception("NeverendingSongs import failed: {error}", error=error)
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


def _fetch_payload(url: str) -> FetchedPayload:
    try:
        with urlopen(url, timeout=30) as response:  # noqa: S310
            data = response.read()
            headers = response.headers
            status_code = cast(int | None, getattr(response, "status", None))
            content_type = headers.get("Content-Type")
        payload_bytes = cast(bytes, data)
        return FetchedPayload(
            text=payload_bytes.decode("utf-8"),
            status_code=status_code,
            content_type=content_type,
            byte_count=len(payload_bytes),
        )
    except HTTPError as error:
        safe_url = _safe_url_for_logging(url)
        raise RuntimeError(f"HTTP error for source {safe_url}: {error.code}") from error
    except URLError as error:
        safe_url = _safe_url_for_logging(url)
        raise RuntimeError(
            f"URL error for source {safe_url}: {error.reason}"
        ) from error


def _map_payload_with_jq(
    payload: str,
    source_name: str,
    start_iso: str,
    end_iso: str,
    safe_url: str,
) -> list[NeverendingSongsMappedRecord]:
    missing_entry_reason = _missing_result_entry_reason(payload)
    if missing_entry_reason is not None:
        payload_summary = _summarize_payload_for_log(payload)
        message = (
            "source returned no entries: "
            f"source={source_name}, start={start_iso}, end={end_iso}, "
            f"url={safe_url}, {missing_entry_reason}, payload={payload_summary}"
        )
        logger.error("NeverendingSongs {message}", message=message)
        raise RuntimeError(message)

    jq_executable = _ensure_jq_available()

    process = subprocess.run(
        [
            jq_executable,
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
        payload_summary = _summarize_payload_for_log(payload)
        logger.error(
            "NeverendingSongs jq mapping failed: "
            "source={source}, start={start}, end={end}, url={url}, "
            "returncode={returncode}, stderr={stderr}, payload={payload_summary}",
            source=source_name,
            start=start_iso,
            end=end_iso,
            url=safe_url,
            returncode=process.returncode,
            stderr=stderr,
            payload_summary=payload_summary,
        )
        raise RuntimeError(
            "jq mapping failed: "
            f"source={source_name}, start={start_iso}, end={end_iso}, "
            f"url={safe_url}, payload={payload_summary}, stderr={stderr}"
        )

    records: list[NeverendingSongsMappedRecord] = []
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    for line in lines:
        row = json.loads(line)
        records.append(NeverendingSongsMappedRecord.model_validate(row))

    return records


def _missing_result_entry_reason(payload: str) -> str | None:
    try:
        decoded: object = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if not isinstance(decoded, dict):
        return None

    result = decoded.get("result")
    if not isinstance(result, dict):
        return None

    if result.get("entry") is not None:
        return None

    return f"result.entry is missing, found={result.get('found')}"


def _safe_url_for_logging(url: str) -> str:
    parsed = urlsplit(url)
    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        redacted_value = (
            "***"
            if any(marker in key.lower() for marker in SENSITIVE_QUERY_MARKERS)
            else value
        )
        query_items.append((key, redacted_value))
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query_items),
            "",
        )
    )


def _summarize_payload_for_log(payload: str) -> str:
    try:
        decoded: object = json.loads(payload)
    except json.JSONDecodeError:
        return (
            f"text chars={len(payload)}, "
            f"bytes={len(payload.encode('utf-8'))}, "
            f"preview={_payload_preview(payload)}"
        )

    return _summarize_json_for_log(decoded)


def _summarize_json_for_log(value: object) -> str:
    if isinstance(value, dict):
        keys = [str(key) for key in value]
        parts = [f"json.object keys={_format_list_preview(keys)}"]
        if "result" in value:
            parts.append(f"result={_summarize_json_node(value['result'])}")
        return ", ".join(parts)

    return f"json.{_summarize_json_node(value)}"


def _summarize_json_node(value: object) -> str:
    if isinstance(value, dict):
        keys = [str(key) for key in value]
        entry_summary = ""
        if "entry" in value:
            entry_summary = f", entry={_summarize_json_node(value['entry'])}"
        return f"object keys={_format_list_preview(keys)}{entry_summary}"
    if isinstance(value, list):
        if not value:
            return "array len=0"
        return f"array len={len(value)}, first={_summarize_json_node(value[0])}"
    if value is None:
        return "null"
    if isinstance(value, str):
        return f"string len={len(value)}"
    if isinstance(value, bool):
        return f"boolean value={value}"
    if isinstance(value, int | float):
        return f"number value={value}"
    return type(value).__name__


def _format_list_preview(values: list[str]) -> str:
    visible_values = values[:SUMMARY_ITEM_LIMIT]
    suffix = (
        ""
        if len(values) <= SUMMARY_ITEM_LIMIT
        else f", ... +{len(values) - SUMMARY_ITEM_LIMIT}"
    )
    return "[" + ", ".join(visible_values) + suffix + "]"


def _payload_preview(payload: str) -> str:
    normalized = " ".join(payload.split())
    return repr(normalized[:PAYLOAD_PREVIEW_CHARS])


def _ensure_jq_available() -> str:
    jq_executable = shutil.which("jq")
    if jq_executable is None:
        raise RuntimeError(
            "jq is required for NeverendingSongs import but was not found on PATH. "
            "Install jq first (macOS: `brew install jq`, Debian/Ubuntu: `apt install jq`)."
        )
    return jq_executable


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
    details: str | None,
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
