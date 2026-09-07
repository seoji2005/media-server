"""Transactional SQLite upgrades, including pre-versioned local libraries."""
from .storage import MediaError
import re
import uuid

VERSION = 7


def companion_identity(db):
    rows = db.execute('SELECT slot,server_id,library_id FROM companion_identity').fetchall()
    if (len(rows) != 1 or rows[0]['slot'] != 1
            or any(not isinstance(rows[0][key], str) or not re.fullmatch('[0-9a-f]{32}', rows[0][key])
                   for key in ('server_id', 'library_id'))):
        raise MediaError('library_identity_invalid', 503)
    return {'version': 1, 'product': 'media-server',
            'server_id': rows[0]['server_id'], 'library_id': rows[0]['library_id']}


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


def _previews(db):
    _statements(db, '''
        CREATE TABLE IF NOT EXISTS preview_sets (
            id TEXT PRIMARY KEY, item_id TEXT NOT NULL UNIQUE REFERENCES items(id),
            input_sha TEXT NOT NULL, duration REAL NOT NULL, total INTEGER NOT NULL,
            profile TEXT NOT NULL, start REAL NOT NULL, seek_offset REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS preview_frames (
            set_id TEXT NOT NULL REFERENCES preview_sets(id), ordinal INTEGER NOT NULL,
            time REAL NOT NULL, image BLOB, sha256 TEXT, error TEXT,
            PRIMARY KEY(set_id,ordinal)
        );
    ''')


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
        if version < 3:
            _previews(db)
        if version < 4:
            db.execute('''CREATE TABLE IF NOT EXISTS scene_vectors (
                set_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
                model_sha TEXT NOT NULL, frame_sha TEXT NOT NULL,
                vector BLOB NOT NULL, sha256 TEXT NOT NULL,
                PRIMARY KEY(set_id,ordinal),
                FOREIGN KEY(set_id,ordinal) REFERENCES preview_frames(set_id,ordinal)
            )''')
        if version < 5:
            _add(db, 'subtitle_jobs', 'asr_completed', 'INTEGER NOT NULL DEFAULT 0')
            _add(db, 'subtitle_jobs', 'asr_until', 'REAL NOT NULL DEFAULT 0')
            db.execute('''CREATE TABLE IF NOT EXISTS asr_spans (
                job_id TEXT NOT NULL REFERENCES subtitle_jobs(id), ordinal INTEGER NOT NULL,
                payload TEXT NOT NULL, sha256 TEXT NOT NULL,
                PRIMARY KEY(job_id,ordinal)
            )''')
        if version < 6:
            _add(db, 'subtitle_jobs', 'source_track_id', 'TEXT REFERENCES subtitle_tracks(id)')
        if version < 7:
            db.execute('''CREATE TABLE IF NOT EXISTS companion_identity (
                slot INTEGER PRIMARY KEY CHECK(slot=1),
                server_id TEXT NOT NULL, library_id TEXT NOT NULL
            )''')
            if not db.execute('SELECT 1 FROM companion_identity').fetchone():
                db.execute('INSERT INTO companion_identity VALUES(1,?,?)',
                           (uuid.uuid4().hex, uuid.uuid4().hex))
        companion_identity(db)  # Current missing/corrupt identity must not regenerate.
        db.execute(f'PRAGMA user_version={VERSION}')
        db.commit()
    except BaseException:
        db.rollback()
        raise
