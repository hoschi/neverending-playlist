# Rules for Writing Tests

- **Vollständige Abdeckung:** Jede neue Funktion in `src/` benötigt einen Unit-Test in `tests/` der alle Fälle abdeckt. Die Coverage wird überprüft.
- **Test Data Generation:** Erstelle **IMMER** Testdaten für Pydantic-Modelle mit `Polyfactory`. Schreibe keine manuellen Dictionaries.
  - *Zweck:* Um Boilerplate zu reduzieren und sicherzustellen, dass Testdaten immer valide sind.
- **Property-Based Testing PBT:** PBT ergänzt Unit-Tests, ersetzt sie aber nicht. Es eignet sich besonders für reine Funktionen, Datenstrukturen und Algorithmen mit universellen Invarianten (z. B. Kommutativität, Assoziativität, Round-Trip-Encode/Decode). Hypothesis generiert automatisch zufällige Eingaben, entdeckt Edge Cases und schrinkt fehlerhafte Beispiele zum minimalen Gegenbeispiel ein. PBT lohnt sich, wenn man bereits umfangreiche @pytest.mark.parametrize-Tests hat, komplexe Geschäftslogik oder zuverlässige Referenzimplementierungen zum Vergleich einsetzt. Nicht geeignet ist PBT bei Seiteneffekten, performanzkritischen Tests oder wenn sich keine klaren Eigenschaften formulieren lassen. Beginne mit klassischen Unit-Tests und abstrahiere wiederkehrende Eingabemuster in Property-Tests.
  - *Zweck:* Um die Robustheit über tausende von Fällen zu beweisen, nicht nur Einzelfälle.
- **Mocking:** Verwende **IMMER** Test-Doubles, die dem `Protocol` der Abhängigkeit entsprechen. Nutze keine Magie-Mocks ohne Spezifikation.
  - *Zweck:* Um sicherzustellen, dass Mocks und echter Code synchron bleiben.
- **Coverage:** Die Code Abdeckung kann nur analysiert werden wenn `pytest` ohne Pfadangabe einer Testdatei verwendet wird! Generell ist es immer besser `pytest` zu verwenden ohne einen spezifische Testdatei um eine fehlerfreie Ausführung zu garantieren.
- **Pydantic Models:** Müssen nur getestet werden wenn Logik existiert die getestet werden kann. Modelle die mit standard `Field` Instanzen beschrieben werden, müssen nicht getestet werden. Wir wollen ja nicht testen ob Pydantic funktioniert, wir wollen nur testen ob unsere Logik die wir schreiben funktioniert.
- **Test Driven Development:** Wenn tests existieren zu der vorliegenden Aufgabe ändere diese zu erst und danach die Implementierung um sicher zu gehen das die Tests auch korrekt funktionieren. Durch die fehlende Implementierung müssten die Tests fehlschlagen. Wenn sie das nicht tun analysiere wieso das so ist und ob hier etwas im Test fehlt. Wenn die Aufgabe komplex ist oder noch keine Tests existieren für die vorliegende Aufgabe schreibe erst die Implementierung und danach den Test.

## Projektspezifisch

### Automatische Mock-Settings
- Tests verwenden automatisch Mock-Settings durch `@pytest.fixture(autouse=True)` in `tests/conftest.py`
- Keine `.env` oder `.env.test` Datei erforderlich für Tests
- Alle Tests laufen erfolgreich auch ohne lokale Konfigurationsdateien
- Mock-Umgebung wird automatisch für alle Tests gesetzt

### Production vs Testing
- **Production**: App stürzt korrekt ab bei fehlender `.env` Datei (mit klarer Fehlermeldung)
- **Testing**: Automatische Mock-Settings durch autouse fixture
- Tests verwenden niemals echte API-Credentials oder echte Services

### Service-Mocking
- **Spotify OAuth**: Immer gemockt (`MockSpotifyOAuth`)
- **Supabase Client**: Immer gemockt (`MockSupabaseClient`)
- **Spotify Client**: Immer gemockt (`MockSpotifyClient`)
- Alle externen Services werden vollständig gemockt für deterministische Tests

### CI-Environment
- Tests funktionieren in CI ohne lokale `.env` Datei
- Automatische Mock-Settings ermöglichen deterministische Test-Ausführung
- Keine Konfigurationsdateien erforderlich

### Mock-Settings Varianten
- **Standard Settings**: Mit Autofill (`playlist_autofill_count=150`) für normale Tests
- **No-Autofill Settings**: Für Edge-Case Tests (`playlist_autofill_count=None`)
- **Cache Management**: Settings-Cache wird vor/nach jedem Test geleert
- **Flexible Testing**: Verschiedene Mock-Fixtures für spezifische Test-Szenarien

### Wann Mock-Settings verwenden
- **Alle Unit-Tests**: Automatisch durch `mock_environment` fixture
- **Integration-Tests**: Automatisch durch autouse, keine manuelle Konfiguration nötig
- **Edge-Case Tests**: Verwende `mock_settings_no_autofill` fixture für spezielle Szenarien
- **Performance Tests**: Mock-Settings ermöglichen schnelle, isolierte Tests ohne externe API-Aufrufe

### Best Practices für Mock-Tests
- **Determinismus**: Mock-Settings garantieren reproduzierbare Testergebnisse
- **Isolation**: Tests sind vollständig isoliert von externen Services
- **Sicherheit**: Keine echten Credentials in Tests oder CI
- **Wartbarkeit**: Automatisches Mocking reduziert Test-Boilerplate
- **Coverage**: 100% Test-Coverage möglich ohne externe Abhängigkeiten