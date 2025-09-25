# Rules for Writing Tests

- **Vollständige Abdeckung:** Jede neue Funktion in `src/` benötigt einen Unit-Test in `tests/` der alle Fälle abdeckt. Die Coverage wird überprüft.
- **Test Data Generation:** Erstelle **IMMER** Testdaten für Pydantic-Modelle mit `Polyfactory`. Schreibe keine manuellen Dictionaries.
  - *Zweck:* Um Boilerplate zu reduzieren und sicherzustellen, dass Testdaten immer valide sind.
- **Property-Based Testing PBT:** PBT ergänzt Unit-Tests, ersetzt sie aber nicht. Es eignet sich besonders für reine Funktionen, Datenstrukturen und Algorithmen mit universellen Invarianten (z. B. Kommutativität, Assoziativität, Round-Trip-Encode/Decode). Hypothesis generiert automatisch zufällige Eingaben, entdeckt Edge Cases und schrinkt fehlerhafte Beispiele zum minimalen Gegenbeispiel ein. PBT lohnt sich, wenn man bereits umfangreiche @pytest.mark.parametrize-Tests hat, komplexe Geschäftslogik oder zuverlässige Referenzimplementierungen zum Vergleich einsetzt. Nicht geeignet ist PBT bei Seiteneffekten, performanzkritischen Tests oder wenn sich keine klaren Eigenschaften formulieren lassen. Beginne mit klassischen Unit-Tests und abstrahiere wiederkehrende Eingabemuster in Property-Tests.
  - *Zweck:* Um die Robustheit über tausende von Fällen zu beweisen, nicht nur Einzelfälle.
- **Mocking:** Verwende **IMMER** Test-Doubles, die dem `Protocol` der Abhängigkeit entsprechen. Nutze keine Magie-Mocks ohne Spezifikation.
  - *Zweck:* Um sicherzustellen, dass Mocks und echter Code synchron bleiben.
