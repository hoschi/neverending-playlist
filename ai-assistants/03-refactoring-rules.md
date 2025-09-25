# Rules for Refactoring Code

- **Ziel: Funktionale Reinheit:** Dein Hauptziel ist es, Side-Effects zu reduzieren und Funktionen reiner zu machen.
- **`try/except` -> `Result`:** Refaktoriere `try/except`-Blöcke in der Business-Logik zu Funktionen, die `returns.Result` zurückgeben.
- **`dict` -> `Pydantic`:** Ersetze rohe Dictionaries, die als Entitäten dienen, durch stark typisierte `Pydantic`-Modelle.
- **Harte Abhängigkeiten -> `Protocol`:** Wenn eine Funktion eine konkrete Klasse (z.B. einen API-Client) direkt importiert, refaktoriere sie, um stattdessen ein `Protocol` als Argument zu akzeptieren.
