# Rules for Refactoring Code

- **Ziel: Funktionale Reinheit:** Dein Hauptziel ist es, Side-Effects zu reduzieren und Funktionen reiner zu machen.
- **`try/except` -> `Result`:** Refaktoriere `try/except`-Blöcke in der Business-Logik zu Funktionen, die `returns.Result` zurückgeben.
- **`dict` -> `Pydantic`:** Ersetze rohe Dictionaries, die als Entitäten dienen, durch stark typisierte `Pydantic`-Modelle.
- **Harte Abhängigkeiten -> `Protocol` (nur wenn sinnvoll!):** Wenn eine Funktion eine konkrete Klasse (z.B. einen API-Client) direkt importiert, prüfe zuerst, ob mehrere Implementierungen wirklich gebraucht werden (z.B. für Tests, verschiedene Backends). Nur dann refaktoriere auf ein `Protocol` als Argument. In allen anderen Fällen bleibe beim "functional first"-Ansatz (freie Funktionen, reine Datenstrukturen). Das Protocol-Muster ist kein Selbstzweck und darf nicht für einfache Services mit nur einer Implementierung verwendet werden.
