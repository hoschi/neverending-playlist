import asyncio
import contextlib
import sqlite3
from datetime import UTC, datetime

from loguru import logger
from returns.pipeline import is_successful

from src.core.config import Settings
from src.core.models import NeverendingSongsImportStatus
from src.core.services.neverending_scheduler_service import (
    seconds_until_next_hour,
    should_run_daily_import,
)
from src.core.sqlite_schema import IMPORT_RUNS_TABLE, SQLITE_SCHEMA_STATEMENTS
from src.shell.neverending_songs import run_neverending_songs_import


class NeverendingScheduler:
    """Hourly scheduler with daily 02:00 run and catch-up behavior."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            logger.info("NeverendingScheduler already running")
            return

        if self._shutdown_event.is_set():
            self._shutdown_event.clear()

        self._task = asyncio.create_task(self._run_loop())
        logger.info("NeverendingScheduler started")

    async def stop(self) -> None:
        if not self._task:
            logger.info("NeverendingScheduler not running")
            return

        self._shutdown_event.set()
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task

        self._task = None
        logger.info("NeverendingScheduler stopped")

    async def run_check_once(self, now_local: datetime | None = None) -> bool:
        """Runs one scheduler check and returns whether an import was triggered."""
        current_local = now_local or datetime.now().astimezone()
        last_success = self._get_last_successful_run()

        should_run = should_run_daily_import(
            now_local=current_local,
            last_successful_run_at=last_success,
            scheduled_hour=2,
        )

        if not should_run:
            logger.debug(
                "Scheduler check skipped: hour={hour}, last_success={last_success}",
                hour=current_local.hour,
                last_success=last_success.isoformat() if last_success else None,
            )
            return False

        logger.info(
            "Scheduler triggering daily import: local_time={local_time}",
            local_time=current_local.isoformat(),
        )
        result = run_neverending_songs_import(
            source_urls=self.settings.song_source_rest_urls,
            sqlite_db_path=self.settings.sqlite_db_path,
            sqlite_max_size_bytes=self.settings.sqlite_max_size_bytes,
        )

        if not is_successful(result):
            logger.error(
                "Scheduled NeverendingSongs import failed: {error}",
                error=result.failure(),
            )
            return False

        run_summary = result.unwrap()
        logger.info(
            "Scheduled import completed: status={status}, imported={count}",
            status=run_summary.status.value,
            count=run_summary.imported_count,
        )
        return run_summary.status in {
            NeverendingSongsImportStatus.SUCCESS,
            NeverendingSongsImportStatus.SKIPPED_MAX_DB_SIZE,
        }

    async def _run_loop(self) -> None:
        try:
            while not self._shutdown_event.is_set():
                now_local = datetime.now().astimezone()
                wait_seconds = seconds_until_next_hour(now_local)
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=wait_seconds
                    )
                    break
                except TimeoutError:
                    await self.run_check_once(now_local=datetime.now().astimezone())
        except asyncio.CancelledError:
            logger.info("NeverendingScheduler task cancelled")
        except Exception as error:
            logger.error("NeverendingScheduler crashed: {error}", error=error)
        finally:
            logger.info("NeverendingScheduler loop exited")

    def _get_last_successful_run(self) -> datetime | None:
        connection = sqlite3.connect(self.settings.sqlite_db_path)
        try:
            cursor = connection.cursor()
            for statement in SQLITE_SCHEMA_STATEMENTS:
                cursor.execute(statement)
            connection.commit()

            row = cursor.execute(
                f"""
                SELECT run_at
                FROM {IMPORT_RUNS_TABLE}
                WHERE status = ?
                ORDER BY run_at DESC
                LIMIT 1
                """,
                (NeverendingSongsImportStatus.SUCCESS.value,),
            ).fetchone()
            if row is None:
                return None
            return datetime.fromisoformat(str(row[0])).astimezone(UTC)
        finally:
            connection.close()
