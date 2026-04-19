SONG_REQUESTS_TABLE = "song_requests"
IMPORT_RUNS_TABLE = "neverending_songs_runs"

SONG_REQUESTS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {SONG_REQUESTS_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist TEXT NOT NULL,
    song TEXT NOT NULL,
    status TEXT,
    requested_by TEXT,
    airtime TEXT NOT NULL,
    source TEXT NOT NULL,
    external_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source, airtime, artist, song)
);
""".strip()

IMPORT_RUNS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {IMPORT_RUNS_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    status TEXT NOT NULL,
    imported_count INTEGER NOT NULL DEFAULT 0,
    source_count INTEGER NOT NULL DEFAULT 0,
    details TEXT
);
""".strip()

SQLITE_SCHEMA_STATEMENTS = (
    SONG_REQUESTS_SCHEMA,
    IMPORT_RUNS_SCHEMA,
)
