# 5. Functional Core, Imperative Shell (FCIS)

## Kernkonzept
Das FCIS Pattern teilt Software in **zwei klare Schichten**:

**Functional Core (Funktionaler Kern):**
- Enthält **alle Geschäftslogik** als pure functions
- **Keine Seiteneffekte** (kein I/O, keine Mutability)
- `../src/core/`

**Imperative Shell (Imperative Schale):**
- Behandelt **alle Seiteneffekte**: I/O, Datenbank, HTTP, Logging
- Orchestriert Aufrufe zum funktionalen Kern
- Sollte **möglichst dünn** gehalten werden
- `../src/shell/`

## Architektur-Prinzipien
1. **Unidirektionale Abhängigkeit**: Shell → Core (niemals umgekehrt)
2. **Seiteneffekte minimieren**: Alle unreinen Operationen an den Rand drängen
3. **Domain Logic im Core**: Geschäftsregeln bleiben rein und testbar

## Typischer Ablauf
```
Eingabe → Shell → Core (reine Berechnung) → Shell → Ausgabe
```

Die Shell:
1. Empfängt externe Eingaben
2. Konvertiert zu reinen Datenstrukturen
3. Ruft funktionalen Kern auf
4. Führt Seiteneffekte basierend auf Ergebnis aus

## Ausnahmen

* logging ist auch im Kern erlaubt
