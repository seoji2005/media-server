"""Transactional SQLite upgrades, including pre-versioned local libraries."""
from .storage import MediaError

VERSION = 2


def _statements(db, sql):
    # These schema statements contain no triggers; avoid executescript's implicit COMMIT.
    for statement in sql.split(';'):
        if statement.strip():
            db.execute(statement)


def _add(db, table, name, definition):
    if name not in {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}:
        db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')


def _legacy_storage(db):
    _statements(db, """
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL, extension TEXT NOT NULL,
            mime TEXT NOT NULL, duration REAL NOT NULL,
            width INTEGER NOT NULL, height INTEGER NOT NULL,
            thumbnail INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY, file_id TEXT NOT NULL UNIQUE REFERENCES files(id),
            title TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            position REAL NOT NULL DEFAULT 0,
            watched_at TEXT
        );
        CREATE TABLE IF NOT EXISTS renditions (
            id TEXT PRIMARY KEY, item_id TEXT NOT NULL UNIQUE REFERENCES items(id),
            input_sha TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
            extension TEXT NOT NULL, mime TEXT NOT NULL, kind TEXT NOT NULL, duration REAL
        );
    """)
    columns = {r['name'] for r in db.execute('PRAGMA table_info(files)')}
    if 'preparation' not in columns:
        db.execute("ALTER TABLE files ADD COLUMN preparation TEXT NOT NULL DEFAULT 'unchecked'")
    if 'preparation_error' not in columns:
        db.execute('ALTER TABLE files ADD COLUMN preparation_error TEXT')
    if 'duration' not in {r['name'] for r in db.execute('PRAGMA table_info(renditions)')}:
        db.execute('ALTER TABLE renditions ADD COLUMN duration REAL')

def _legacy_subtitles(db):
    _statements(db, '''
        CREATE TABLE IF NOT EXISTS subtitle_jobs (
            id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id),
            input_sha TEXT NOT NULL, state TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'asr',
            attempt INTEGER NOT NULL DEFAULT 0, completed INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0, error TEXT,
            config_sha TEXT, transcript TEXT, transcript_sha TEXT, translation_sha TEXT, translation TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_subtitle_job ON subtitle_jobs(item_id)
            WHERE state IN ('queued','running','paused');
        CREATE TABLE IF NOT EXISTS subtitle_tracks (
            id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id),
            input_sha TEXT NOT NULL, job_id TEXT UNIQUE REFERENCES subtitle_jobs(id),
            source TEXT NOT NULL, cues TEXT NOT NULL, sha256 TEXT NOT NULL, source_srt BLOB,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
        CREATE TABLE IF NOT EXISTS subtitle_batches (
            job_id TEXT NOT NULL REFERENCES subtitle_jobs(id), first_index INTEGER NOT NULL,
            payload TEXT NOT NULL, sha256 TEXT NOT NULL,
            PRIMARY KEY(job_id,first_index)
        );
    ''')
    columns = {r['name'] for r in db.execute('PRAGMA table_info(subtitle_tracks)')}
    if 'source_srt' not in columns:
        db.execute('ALTER TABLE subtitle_tracks ADD COLUMN source_srt BLOB')
    if 'warnings' not in columns:
        db.execute('ALTER TABLE subtitle_tracks ADD COLUMN warnings TEXT')
    if 'presentation' not in columns:
        db.execute('ALTER TABLE subtitle_tracks ADD COLUMN presentation TEXT')
    if 'presentation_summary' not in columns:
        db.execute('ALTER TABLE subtitle_tracks ADD COLUMN presentation_summary TEXT')
    columns = {r['name'] for r in db.execute('PRAGMA table_info(subtitle_jobs)')}
    if 'fallback_count' not in columns:
        db.execute('ALTER TABLE subtitle_jobs ADD COLUMN fallback_count INTEGER NOT NULL DEFAULT 0')

def _legacy_recommendations(db):
    db.execute("""CREATE TABLE IF NOT EXISTS item_preferences (
        item_id TEXT PRIMARY KEY REFERENCES items(id),
        included INTEGER NOT NULL DEFAULT 0 CHECK(included IN (0,1)),
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
        preference TEXT NOT NULL DEFAULT 'neutral'
            CHECK(preference IN ('neutral','like','dislike','less'))
    )""")
    if 'revision' not in {row['name'] for row in db.execute('PRAGMA table_info(item_preferences)')}:
        db.execute('ALTER TABLE item_preferences ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')


def _audio_tracks(db):
    _add(db, 'files', 'audio_tracks', 'TEXT')
    _add(db, 'items', 'audio_index', 'INTEGER NOT NULL DEFAULT 0 CHECK(audio_index>=0)')
    _add(db, 'subtitle_jobs', 'audio_index', 'INTEGER NOT NULL DEFAULT 0 CHECK(audio_index>=0)')
    _add(db, 'subtitle_tracks', 'audio_index', 'INTEGER NOT NULL DEFAULT 0 CHECK(audio_index>=0)')
    if 'audio_index' not in {r['name'] for r in db.execute('PRAGMA table_info(renditions)')}:
        db.execute('ALTER TABLE renditions RENAME TO renditions_v1')
        db.execute('''CREATE TABLE renditions (
            id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id),
            input_sha TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
            extension TEXT NOT NULL, mime TEXT NOT NULL, kind TEXT NOT NULL, duration REAL,
            audio_index INTEGER NOT NULL DEFAULT 0 CHECK(audio_index>=0),
            UNIQUE(item_id,audio_index)
        )''')
        db.execute('INSERT INTO renditions SELECT *,0 FROM renditions_v1')
        db.execute('DROP TABLE renditions_v1')


def migrate(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > VERSION:
            raise MediaError('database_version_newer', 503)
        if version < 1:
            _legacy_storage(db)
            _legacy_subtitles(db)
            _legacy_recommendations(db)
        if version < 2:
            _audio_tracks(db)
        db.execute(f'PRAGMA user_version={VERSION}')
        db.commit()
    except BaseException:
        db.rollback()
        raise
