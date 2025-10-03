# Update Current State Documentation

## Wann diese Datei aktualisiert werden muss

**IMMER** nach jeder Änderung im `src/` Verzeichnis:
- Neue Dateien erstellt
- Bestehende Dateien geändert (jede Änderung, nicht nur signifikante)
- Dateien gelöscht
- Dateien umbenannt oder verschoben
- Funktionen, Klassen oder Module hinzugefügt/entfernt/geändert

## Was zu aktualisieren ist

### Bei neuen Dateien
- Datei zur entsprechenden Sektion hinzufügen
- Beschreibung in maximal 50 Wörtern erstellen
- Format: `- **`dateiname.py`** - Beschreibung`
- Alphabetische Sortierung innerhalb der Sektion beibehalten

### Bei geänderten Dateien
- Bestehende Beschreibung überprüfen und aktualisieren
- Sicherstellen dass die Beschreibung die aktuelle Funktionalität widerspiegelt
- 50-Wörter-Regel einhalten
- Neue Funktionen, Klassen oder wichtige Änderungen erwähnen

### Bei gelöschten Dateien
- Entsprechenden Eintrag komplett aus current-state.md entfernen
- Prüfen ob andere Beschreibungen Referenzen zur gelöschten Datei enthalten
- Diese Referenzen ebenfalls entfernen oder aktualisieren

### Bei umbenannten/verschobenen Dateien
- Dateiname und Pfad in der Beschreibung aktualisieren
- Sektion wechseln falls Datei zwischen core/ und shell/ verschoben wurde
- Beschreibung anpassen falls sich die Funktion geändert hat

## Repository Overview Updates

### Features implementiert
- Implementierte Funktionalitäten auflisten
- Setup-Teile von Feature-Teilen unterscheiden

### Architektur-Änderungen
- FCIS-Struktur anpassen falls sich die Organisation ändert
- Neue Module oder Packages dokumentieren
- Veränderte Abhängigkeiten zwischen Core und Shell reflektieren

## Format-Regeln

### Datei-Beschreibungen
- Maximal 50 Wörter pro Datei
- Fokus auf Hauptfunktion der Datei
- Wichtige Klassen, Funktionen oder Konzepte erwähnen
- Zweck und Rolle im Gesamtsystem erklären

### Struktur-Konsistenz
- Core-Module vor Shell-Module
- Alphabetische Sortierung innerhalb jeder Sektion
- Einheitliche Markdown-Formatierung
- Hierarchische Organisation beibehalten

## Workflow für KI Agenten

### Nach jeder src/ Änderung
1. Aktuelle `ai-assistants/current-state.md` lesen
2. Alle geänderten, neuen oder gelöschten Dateien identifizieren
3. Entsprechende Sektionen in current-state.md lokalisieren
4. Beschreibungen prüfen und bei Bedarf aktualisieren
5. Neue Einträge hinzufügen oder gelöschte entfernen
6. 50-Wörter-Regel für alle Beschreibungen verifizieren
7. Aktualisierte current-state.md speichern

### Prüfliste
- Sind alle src/ Dateien dokumentiert?
- Stimmen alle Beschreibungen mit dem aktuellen Code überein?
- Sind gelöschte Dateien entfernt?
- Ist die alphabetische Sortierung korrekt?
- Sind alle Beschreibungen unter 50 Wörtern?
- Ist die Repository Overview aktuell?

## Was NICHT dokumentiert wird

- Test-Dateien im tests/ Verzeichnis
- Konfigurationsdateien außerhalb von src/
- Build-Artefakte oder temporäre Dateien
- AI-Assistant Regeln außer current-state.md
- Dokumentationsdateien außerhalb von src/