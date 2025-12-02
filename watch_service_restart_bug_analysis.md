# WatchService Restart Bug - Root Cause Analysis & Fix Strategy

## Bug Summary
**Problem**: WatchService kann nicht neu gestartet werden nach Retry-Erschöpfung  
**Symptom**: API behauptet Service erfolgreich gestartet, aber Service stoppt sofort  
**Impact**: Benutzer können WatchService nicht über `/clear-played-watchmode` neu starten  

## Root Cause Analysis

### 1. Hauptproblem: Inkonsistente Retry-Logik in `start_watch_service()`

**Problem-Location**: `src/shell/watch_service.py:74-77`

```python
if current_state.retries_left <= 1:
    raise ValueError(
        "No active playback detected. WatchService not started."
    )
```

**Das Problem**:
- Der Check `current_state.retries_left <= 1` erfolgt VOR der Retry-Reset-Logik
- Wenn `retries_left=0` (nach erschöpften Retries), schlägt der Restart fehl
- Selbst wenn Active Playback verfügbar ist, wird ValueError geworfen

### 2. Sekundärproblem: Retry-Counter wird nicht korrekt zurückgesetzt

**Problem-Location**: `src/shell/watch_service.py:85-92`

```python
await update_checker_state(
    is_running=True,
    retries_left=5,  # Reset auf 5
    last_playback_detected=True,
    next_check=datetime.now(UTC) + timedelta(minutes=settings.watch_service_timeout_minutes),
)
```

**Das Problem**:
- Der Retry-Reset auf 5 passiert nur WENN der Check erfolgreich ist
- Wenn `retries_left <= 1`, wird ValueError geworfen BEVOR Reset erfolgt
- State bleibt mit `retries_left=0` zurück, Service kann nie neu starten

### 3. State Management Inkonsistenz

**Problem**:
- API-Response zeigt `is_running=True` (Service gestartet)
- Aber `retries_left=0` bedeutet Service stoppt beim nächsten Check
- `_execute_clear_task()` ruft `stop_watch_service()` auf bei `retries_left <= 1`
- Dies erstellt die gemeldete Inkonsistenz: "API sagt läuft, Service stoppt"

## Detaillierte Bug-Rekonstruktion

### Szenario 1: Service stoppt nach erschöpften Retries
1. WatchService läuft mit 5 Retries
2. 5x hintereinander kein Active Playback erkannt
3. `_execute_clear_task()` decrementiert `retries_left` auf 0
4. Bei 6. Check: `retries_left=0`, Service ruft `stop_watch_service()` auf
5. State: `is_running=False, retries_left=0`

### Szenario 2: Restart-Versuch schlägt fehl  
1. Benutzer ruft `/clear-played-watchmode` Endpoint auf
2. `start_watch_service()` wird aufgerufen
3. Checkt `current_state.retries_left <= 1` → `0 <= 1` ist TRUE
4. ValueError wird geworfen: "No active playback detected"
5. Service kann nicht gestartet werden
6. **BUG**: Error-Message ist irreführend - Playback ist verfügbar!

### Szenario 3: Service startet aber stoppt sofort (wenn Mock-Workaround)
1. In Tests: Mocks können den Check umgehen
2. Service "startet" erfolgreich 
3. State zeigt `is_running=True, retries_left=0`
4. `_execute_clear_task()` läuft einmal, decrementiert auf negative Zahl
5. Nächster Check: `retries_left < 0`, Service stoppt sich selbst
6. **Ergebnis**: API sagt "gestartet", Service ist sofort wieder gestoppt

## Fix-Strategie

### Option 1: Retry-Reset vor Check (EMPFOHLEN)

```python
async def start_watch_service(self) -> CheckerState:
    """Starts the Background WatchService Task."""
    current_state = await get_checker_state()

    if current_state.is_running:
        logger.info("WatchService already running, returning current state")
        return current_state

    try:
        # FIX: Reset retry counter FIRST, then check playback
        # If current retries are low, reset to 5 for a fresh start
        if current_state.retries_left < 5:
            logger.info(f"Resetting retry counter from {current_state.retries_left} to 5")
            await update_checker_state(retries_left=5)

        # Check for active playback after reset
        if not await self._check_active_playback():
            new_retries_left = max(0, current_state.retries_left - 1)
            await update_checker_state(retries_left=new_retries_left)

            if new_retries_left <= 0:
                raise ValueError(
                    "No active playback detected after retry reset. WatchService not started."
                )
            else:
                logger.warning(
                    f"No active playback detected. Retries left: {new_retries_left}"
                )
                return await get_checker_state()

        # Continue with successful start...
        settings = get_settings()
        await update_checker_state(
            is_running=True,
            retries_left=5,  # This becomes redundant but safe
            last_playback_detected=True,
            next_check=datetime.now(UTC) + timedelta(minutes=settings.watch_service_timeout_minutes),
        )
        
        # Start background task
        self._task = asyncio.create_task(self._watch_loop())
        
        return await get_checker_state()

    except Exception as e:
        logger.error(f"Error starting WatchService: {e}")
        await update_checker_state(is_running=False)
        raise
```

**Vorteile**:
- Benutzer können Service immer neu starten wenn Playback verfügbar
- Retry-Counter wird bei Restart automatisch zurückgesetzt
- Klare Logik: "Try to restart, reset retries, check playback"
- Keine Breaking Changes

### Option 2: Separate Restart-Logik

```python
async def restart_watch_service(self) -> CheckerState:
    """Restart WatchService with fresh retry counter."""
    current_state = await get_checker_state()
    
    # If running, stop first
    if current_state.is_running:
        await self.stop_watch_service()
    
    # Reset to fresh state
    await update_checker_state(
        is_running=False,
        retries_left=5,  # Fresh start
        last_playback_detected=False,
        last_checked=None,
        next_check=None
    )
    
    # Now start normally
    return await self.start_watch_service()
```

**Vorteile**:
- Explizite Restart-Funktion
- Saubere Trennung von Start/Restart-Logik
- API-Endpoint kann `restart_watch_service()` statt `start_watch_service()` aufrufen

**Nachteile**:
- API-Änderung erforderlich
- Mehr komplexer Code

### Option 3: Adaptive Retry-Logik

```python
async def start_watch_service(self) -> CheckerState:
    """Starts the Background WatchService Task."""
    current_state = await get_checker_state()

    if current_state.is_running:
        logger.info("WatchService already running, returning current state")
        return current_state

    try:
        # Check if this is a restart attempt with exhausted retries
        is_restart_attempt = current_state.retries_left <= 1 and not current_state.is_running
        
        # For restart attempts, be more lenient with playback requirements
        if is_restart_attempt:
            logger.info("Detected restart attempt with low retries, checking playback...")
            
            if not await self._check_active_playback():
                raise ValueError(
                    "No active playback detected. Service cannot restart without active playback."
                )
            
            # Reset retries for successful restart
            await update_checker_state(retries_left=5)
        else:
            # Normal start logic
            if not await self._check_active_playback():
                new_retries_left = max(0, current_state.retries_left - 1)
                await update_checker_state(retries_left=new_retries_left)

                if current_state.retries_left <= 1:
                    raise ValueError(
                        "No active playback detected. WatchService not started."
                    )
                else:
                    logger.warning(
                        f"No active playback detected. Retries left: {new_retries_left}"
                    )
                    return await get_checker_state()

        # Continue with successful start...
        # ... rest of start logic
        
    except Exception as e:
        logger.error(f"Error starting WatchService: {e}")
        await update_checker_state(is_running=False)
        raise
```

**Vorteile**:
- Adaptive Logik für verschiedene Szenarien
- Behält bestehende Validierung bei
- Ermöglicht Restart bei Playback-Verfügbarkeit

**Nachteile**:
- Komplexere Logik
- Schwerer zu verstehen und zu testen

## Empfehlung

**Option 1** (Retry-Reset vor Check) ist der beste Ansatz:

1. ✅ **Einfach zu implementieren**: Nur wenige Codezeilen ändern
2. ✅ **Intuitive Logik**: "Wenn niedrige Retries, reset auf 5, dann starte"
3. ✅ **Keine API-Änderungen**: Bestehende `/clear-played-watchmode` Endpoint funktioniert
4. ✅ **Bug-freundlich**: Benutzer können Service immer neu starten wenn Playback verfügbar
5. ✅ **Testbar**: Klare Testfälle für Retry-Reset-Verhalten

## Implementation Steps

1. **Phase 1**: Option 1 in `start_watch_service()` implementieren
2. **Phase 2**: Bestehende Tests erweitern um Retry-Reset zu testen  
3. **Phase 3**: Integration Test für komplettes Restart-Szenario
4. **Phase 4**: Verification mit echten Server-Logs

## Test Coverage für Fix

```python
async def test_watch_service_restart_resets_retries(watch_service_instance):
    """Test that restart properly resets retry counter to 5."""
    # Setup exhausted state
    # Mock playback available
    # Call start_watch_service()  
    # Verify retries_left = 5 in result

async def test_watch_service_restart_fails_without_playback(watch_service_instance):
    """Test that restart fails when no playback available."""
    # Setup exhausted state
    # Mock no playback available
    # Call start_watch_service()
    # Verify ValueError is raised with proper message
```

## Verification Strategy

1. **Unit Tests**: Retry-Reset-Logik direkt testen
2. **Integration Tests**: Komplettes Restart-Szenario
3. **Manual Testing**: Mit echten Server-Logs verifizieren
4. **Edge Cases**: 0, 1, 2+ Retries bei Restart testen

Dieser Ansatz löst den Root-Cause des Bugs und ermöglicht Benutzern den Service ordnungsgemäß neu zu starten.