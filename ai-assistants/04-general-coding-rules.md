# General Coding Rules

- **Functional First:** Schreibe reine Funktionen, wann immer möglich. Vermeide Klassen für reine Datenstrukturen. Setze das Muster "functional core, imperative shell" um, details dazu findest du in `ai-assistants/05-fcis.md`
- **Strict Typing:** Jeder Code muss vollständig mit `MyPy` im `strict`-Modus validieren. Vermeide `Any`.
- **Error Handling:** Verwende **IMMER** `returns` für Operationen, die fehlschlagen können. Wirf keine Exceptions für erwartbare Fehler.
  - *Zweck & Beispiel:* Um sicherzustellen, dass alle Fehlerfälle im Typsystem abgebildet und behandelt werden müssen. Siehe die lauffähigen Beispiele in `docs/01_core_concepts.ipynb`.
- **Data Boundaries:** Validiere **ALLE** externen Daten (API-Responses, DB-Queries, User-Input) mit `Pydantic`-Modellen an den Rändern der Anwendung. Verwende `Annotated` für detailierte Beschreibungen.
  - *Zweck & Beispiel:* Um eine typsichere Domäne im Inneren der Anwendung zu garantieren. Siehe die Pydantic-Beispiele in `docs/01_core_concepts.ipynb`.
- **Don't Repeat Yourself (DRY):** Vermeide Code-Duplizierung durch die Nutzung von wiederverwendbaren Service-Funktionen und Protokollen.
  - *Zweck & Beispiel:* Um die Wartbarkeit zu erhöhen. Das `Fetcher`-Protocol in `docs/04_architecture_and_design.ipynb` ist ein Beispiel für eine wiederverwendbare Abstraktion.
- Teste deinen Code mit dem Kommando `poe check-all` um sicher zu gehen das alles korrekt ist. Dieses Kommando formatiert den Code, führt die Type Checkes aus sowie die Tests.
- Benutze `Loguru` wenn du logging brauchst um Fehler zu finden oder generell für debug logs die bei bedarf angeschaltet werden können. In `docs/01_core_concepts.ipynb` sind Beispiele zu finden für die Benutzung.
