"""In-Memory WatchService für Clear Played Watchmode Funktionalität.

Dieses Modul implementiert die Background Task Verwaltung für das automatische
Löschen von abgespielten Tracks aus Playlists alle 10 Minuten mit asyncio.
"""

import asyncio
import contextlib
from collections.abc import Callable
from datetime import datetime, timedelta

from loguru import logger
from returns.pipeline import is_successful
from returns.result import Result

from src.core.config import get_settings
from src.core.models import (
    PlaylistClearError,
    PlaylistClearFailure,
)
from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.playlist_service import clear_played_tracks_from_playlist
from src.shell.state import (
    CheckerState,
    get_checker_state,
    reset_checker_state,
    update_checker_state,
)


class WatchService:
    """In-Memory WatchService für Clear Played Watchmode.

    Verwaltet State und Ausführung der automatischen Playlist-Clearing
    Funktionalität, die alle 10 Minuten mit asyncio Tasks läuft.
    """

    def __init__(
        self,
        spotify_client_factory: Callable[[], SpotifyClient],
        supabase_client_factory: Callable[[], SupabaseClient],
    ) -> None:
        """Initialisiert den WatchService mit Client Factories.

        Args:
            spotify_client_factory: Factory-Funktion zum Erstellen von Spotify Clients
            supabase_client_factory: Factory-Funktion zum Erstellen von Supabase Clients
        """
        self.spotify_client_factory = spotify_client_factory
        self.supabase_client_factory = supabase_client_factory
        self._task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()

    async def start_watch_service(self) -> CheckerState:
        """Startet den Background WatchService Task.

        Initiiert den wiederkehrenden Background Task, der nach aktivem Playback
        überwacht und automatisch abgespielte Tracks aus der Playlist alle 10 Minuten löscht.

        Returns:
            CheckerState: Der aktuelle State des WatchService nach dem Start
        """
        current_state = await get_checker_state()

        if current_state.is_running:
            logger.info("WatchService läuft bereits, gebe aktuellen State zurück")
            return current_state

        try:
            # Prüfe auf aktives Playback vor dem Start
            if not await self._check_active_playback():
                new_retries_left = max(0, current_state.retries_left - 1)
                await update_checker_state(retries_left=new_retries_left)

                if current_state.retries_left <= 1:
                    raise ValueError(
                        "Kein aktives Playback erkannt. WatchService nicht gestartet."
                    )
                else:
                    logger.warning(
                        f"Kein aktives Playback erkannt. Verbleibende Versuche: {new_retries_left}"
                    )
                    return await get_checker_state()

            # Setze State auf "gestartet"
            await update_checker_state(
                is_running=True,
                retries_left=5,
                last_playback_detected=True,
                next_check=datetime.utcnow() + timedelta(minutes=10),
            )

            logger.info("WatchService erfolgreich mit asyncio gestartet")

            # Starte Background Task
            self._task = asyncio.create_task(self._watch_loop())

            return await get_checker_state()

        except Exception as e:
            logger.error(f"Fehler beim Starten des WatchService: {e}")
            await update_checker_state(is_running=False)
            raise

    async def stop_watch_service(self) -> CheckerState:
        """Stoppt den Background WatchService Task.

        Returns:
            CheckerState: Der aktuelle State des WatchService nach dem Stoppen
        """
        current_state = await get_checker_state()

        if not current_state.is_running:
            logger.info("WatchService läuft nicht")
            return current_state

        try:
            # Setze Shutdown Event und warte auf Task Beendigung
            self._shutdown_event.set()

            if self._task and not self._task.done():
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._task

            # Setze State auf "gestoppt"
            await update_checker_state(is_running=False, next_check=None)

            logger.info("WatchService erfolgreich gestoppt")

        except Exception as e:
            logger.error(f"Fehler beim Stoppen des WatchService: {e}")
            raise

        return await get_checker_state()

    async def get_state(self) -> CheckerState:
        """Gibt den aktuellen WatchService State zurück.

        Returns:
            CheckerState: Der aktuelle State des WatchService
        """
        return await get_checker_state()

    async def reset_state(self) -> CheckerState:
        """Setzt den WatchService State auf Standardwerte zurück.

        Returns:
            CheckerState: Der zurückgesetzte WatchService State
        """
        # Reset shutdown event
        self._shutdown_event.clear()

        # Cancel any running task
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        # Reset internal state
        self._task = None

        return await reset_checker_state()

    async def _watch_loop(self) -> None:
        """Haupt-Loop für den WatchService Background Task.

        Diese Funktion läuft kontinuierlich und:
        1. Prüft auf aktives Playback
        2. Ruft die bestehende clear_played_tracks_from_playlist Logik auf
        3. Aktualisiert den WatchService State basierend auf Ergebnissen
        4. Behandelt Wiederholungsversuche und Stopp-Bedingungen
        5. Wartet 10 Minuten vor dem nächsten Durchlauf
        """
        logger.info("WatchService Background Task gestartet")

        try:
            while not self._shutdown_event.is_set():
                await self._execute_clear_task()

                # Warte 10 Minuten oder bis Shutdown Signal
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=600.0,  # 10 Minuten
                    )
                    break  # Shutdown Signal erhalten
                except TimeoutError:
                    continue  # 10 Minuten vorbei, nächster Durchlauf

        except asyncio.CancelledError:
            logger.info("WatchService Background Task abgebrochen")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler in WatchService Loop: {e}")
        finally:
            logger.info("WatchService Background Task beendet")

    async def _execute_clear_task(self) -> None:
        """Führt den Background Task zum Löschen abgespielter Tracks aus.

        Hauptfunktion für den Background Task, die:
        1. Auf aktives Playback prüft
        2. Die bestehende clear_played_tracks_from_playlist Logik aufruft
        3. Den WatchService State basierend auf Ergebnissen aktualisiert
        4. Wiederholungsversuche und Stopp-Bedingungen behandelt
        """
        try:
            logger.info("Führe Clear Played Tracks Background Task aus")

            # Aktualisiere last_checked Timestamp
            await update_checker_state(last_checked=datetime.utcnow())

            # Prüfe auf aktives Playback
            active_playback = await self._check_active_playback()
            await update_checker_state(last_playback_detected=active_playback)

            if not active_playback:
                # Behandle Szenario ohne aktives Playback
                current_state = await get_checker_state()
                await update_checker_state(
                    retries_left=max(0, current_state.retries_left - 1)
                )
                logger.warning(
                    f"Kein aktives Playback erkannt. Verbleibende Versuche: {current_state.retries_left - 1}"
                )

                if current_state.retries_left <= 1:
                    logger.error("Keine Versuche mehr übrig, stoppe WatchService")
                    await self.stop_watch_service()
                    return

                return

            # Führe die Clear Played Tracks Logik aus
            await self._clear_played_tracks()

            # Plane nächsten Check
            await update_checker_state(
                next_check=datetime.utcnow() + timedelta(minutes=10)
            )

            logger.info("Background Task erfolgreich abgeschlossen")

        except Exception as e:
            logger.error(f"Fehler in Background Task: {e}")
            current_state = await get_checker_state()
            await update_checker_state(
                retries_left=max(0, current_state.retries_left - 1)
            )

            if current_state.retries_left <= 1:
                logger.error("Keine Versuche mehr wegen Fehlern, stoppe WatchService")
                await self.stop_watch_service()

    async def _check_active_playback(self) -> bool:
        """Prüft, ob eine aktive Playback Session existiert.

        Returns:
            bool: True wenn aktives Playback erkannt wird, False sonst
        """
        try:
            spotify_client = self.spotify_client_factory()
            current_playback_result = await spotify_client.get_current_playback()

            if not is_successful(current_playback_result):
                return False

            current_playback = current_playback_result.unwrap()
            return current_playback is not None

        except Exception as e:
            logger.error(f"Fehler beim Prüfen auf aktives Playback: {e}")
            return False

    async def _clear_played_tracks(self) -> None:
        """Führt die Clear Played Tracks Logik mit bestehendem Service aus.

        Ruft die bestehende clear_played_tracks_from_playlist Funktion
        aus playlist_service.py auf, die die Kern-Business-Logik enthält.
        """
        try:
            settings = get_settings()
            spotify_client = self.spotify_client_factory()
            supabase_client = self.supabase_client_factory()

            # Rufe die bestehende Kern-Logik zum Löschen abgespielter Tracks auf
            result = await clear_played_tracks_from_playlist(
                spotify_client,
                supabase_client,
                settings.spotify_playlist_id,
                settings.playlist_autofill_count,
            )

            if is_successful(result):
                logger.info("Abgespielte Tracks erfolgreich aus Playlist gelöscht")
            else:
                error = result.failure()
                logger.warning(f"Löschen abgespielter Tracks fehlgeschlagen: {error}")

        except Exception as e:
            logger.error(f"Fehler beim Löschen abgespielter Tracks: {e}")
            raise RuntimeError(f"Clear played tracks failed: {e}") from e


async def watch_service(
    supabase_client: SupabaseClient,
    spotify_client: SpotifyClient,
    config_playlist_id: str,
    autofill_count: int | None = None,
) -> Result[dict[str, int], PlaylistClearError]:
    """
    Führt die Watch Service Funktionalität aus - basierend auf dem playlist_service.py Pattern.

    Diese Funktion implementiert das Clear Played Watchmode Feature durch direkte Verwendung
    von Client-Instanzen und Rückgabe eines Result-Typs mit Success/Failure Pattern.

    Args:
        supabase_client: Direkte SupabaseClient Instanz
        spotify_client: Direkte SpotifyClient Instanz
        config_playlist_id: Die konfigurierte Playlist-ID
        autofill_count: Anzahl der Tracks zum automatischen Auffüllen (None = deaktiviert)

    Returns:
        Result[dict[str, int], PlaylistClearError]:
            - Success(dict): Dictionary mit 'deleted_count' und 'filled_count' Schlüsseln
            - Failure(PlaylistClearError): Detaillierte Fehlerinformationen
    """
    logger.info("Starting watch service operation")

    try:
        # Verwende die bestehende clear_played_tracks_from_playlist Logik
        from src.core.services.playlist_service import clear_played_tracks_from_playlist

        result = await clear_played_tracks_from_playlist(
            spotify_client,
            supabase_client,
            config_playlist_id,
            autofill_count,
        )

        if is_successful(result):
            logger.info("Watch service completed successfully")
            return result
        else:
            error = result.failure()
            logger.warning("Watch service failed: {error}", error=error.message)
            return Result.from_failure(error)

    except Exception as e:
        logger.error("Unexpected error in watch service: {error}", error=e)
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.ERROR,
                message="Unexpected error in watch service",
                details=str(e),
            )
        )


_global_watch_service: WatchService | None = None


def get_watch_service(
    spotify_client_factory: Callable[[], SpotifyClient],
    supabase_client_factory: Callable[[], SupabaseClient],
) -> WatchService:
    """Diese Funktion implementiert ein Singleton Pattern, um sicherzustellen,
    dass nur eine WatchService Instanz in der Anwendung läuft.

    Args:
        spotify_client_factory: Factory-Funktion zum Erstellen von Spotify Clients
        supabase_client_factory: Factory-Funktion zum Erstellen von Supabase Clients

    Returns:
        WatchService: Die globale WatchService Instanz
    """
    global _global_watch_service

    if _global_watch_service is None:
        _global_watch_service = WatchService(
            spotify_client_factory, supabase_client_factory
        )

    return _global_watch_service
