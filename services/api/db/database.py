"""SQLite persistence primitives for incident storage.

Kept intentionally small and dependency-free (stdlib ``sqlite3``) so the
repository layer can later be re-implemented against Google Firestore.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from services.api.core import config

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS incidents (
        incident_id TEXT PRIMARY KEY,
        record_id INTEGER NOT NULL,
        product_id TEXT NOT NULL,
        machine_type TEXT NOT NULL,
        algorithm TEXT NOT NULL,
        anomaly_score REAL NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL,
        source_measurements TEXT NOT NULL,
        evidence TEXT NOT NULL,
        explanations TEXT NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS incident_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id TEXT NOT NULL,
        status TEXT NOT NULL,
        note TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES incidents (incident_id)
    )
    """,
    # Prevent duplicate active incidents for the same record + algorithm.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_incident_active
    ON incidents (record_id, algorithm)
    WHERE status != 'resolved'
    """,
    "CREATE INDEX IF NOT EXISTS idx_incident_status ON incidents (status)",
    "CREATE INDEX IF NOT EXISTS idx_incident_severity ON incidents (severity)",
    "CREATE INDEX IF NOT EXISTS idx_incident_record ON incidents (record_id)",
    # --- AI investigation (Step 4) --------------------------------------
    """
    CREATE TABLE IF NOT EXISTS investigations (
        investigation_id TEXT PRIMARY KEY,
        incident_id TEXT NOT NULL,
        status TEXT NOT NULL,
        stage TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        summary TEXT,
        report TEXT,
        error TEXT,
        stage_history TEXT NOT NULL,
        agent_activity TEXT NOT NULL DEFAULT '[]',
        attempt_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES incidents (incident_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS investigation_evidence (
        evidence_id TEXT PRIMARY KEY,
        investigation_id TEXT NOT NULL,
        incident_id TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        source TEXT NOT NULL,
        observation TEXT NOT NULL,
        value REAL,
        units TEXT,
        provenance TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (investigation_id) REFERENCES investigations (investigation_id)
    )
    """,
    # Prevent duplicate *active* investigations for the same incident.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_investigation_active
    ON investigations (incident_id)
    WHERE status IN ('queued', 'running')
    """,
    "CREATE INDEX IF NOT EXISTS idx_investigation_incident ON investigations (incident_id)",
    "CREATE INDEX IF NOT EXISTS idx_investigation_status ON investigations (status)",
    "CREATE INDEX IF NOT EXISTS idx_evidence_investigation ON investigation_evidence (investigation_id)",
]


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or config.settings.database_path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(incidents)")}
            if "detection_config" not in columns:
                connection.execute("ALTER TABLE incidents ADD COLUMN detection_config TEXT")
            connection.commit()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()
