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
        investigation_id TEXT NOT NULL,
        evidence_id TEXT NOT NULL,
        incident_id TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        source TEXT NOT NULL,
        observation TEXT NOT NULL,
        value REAL,
        units TEXT,
        provenance TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (investigation_id, evidence_id),
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
    # --- Counterfactual scenarios (Step 5) ------------------------------
    """
    CREATE TABLE IF NOT EXISTS counterfactual_scenarios (
        scenario_id TEXT PRIMARY KEY,
        original_investigation_id TEXT NOT NULL,
        incident_id TEXT NOT NULL,
        revised_investigation_id TEXT,
        excluded_evidence_ids TEXT NOT NULL,
        excluded_feature_keys TEXT NOT NULL DEFAULT '[]',
        rationale TEXT,
        status TEXT NOT NULL,
        error TEXT,
        comparison TEXT,
        dependency_trace TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (original_investigation_id) REFERENCES investigations (investigation_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_counterfactual_original ON counterfactual_scenarios (original_investigation_id)",
    "CREATE INDEX IF NOT EXISTS idx_counterfactual_incident ON counterfactual_scenarios (incident_id)",
    # --- Visual evidence (Step 5) ---------------------------------------
    """
    CREATE TABLE IF NOT EXISTS visual_evidence (
        image_id TEXT PRIMARY KEY,
        incident_id TEXT NOT NULL,
        investigation_id TEXT,
        storage_ref TEXT NOT NULL,
        filename TEXT NOT NULL,
        mime_type TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        width INTEGER,
        height INTEGER,
        provenance TEXT NOT NULL,
        storage_backend TEXT NOT NULL,
        status TEXT NOT NULL,
        summary TEXT,
        observations TEXT NOT NULL DEFAULT '[]',
        limitations TEXT NOT NULL DEFAULT '[]',
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_visual_incident ON visual_evidence (incident_id)",
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
            self._migrate_evidence_primary_key(connection)
            connection.commit()

    @staticmethod
    def _migrate_evidence_primary_key(connection: sqlite3.Connection) -> None:
        """Rebuild older evidence tables keyed only by ``evidence_id``.

        Counterfactual revisions intentionally reuse the original evidence IDs
        under a new investigation, which requires a composite primary key. Older
        databases stored evidence globally unique, so we recreate the table and
        copy the existing rows across.
        """
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='investigation_evidence'"
        ).fetchone()
        if row is None or "PRIMARY KEY (investigation_id" in (row["sql"] or ""):
            return
        connection.execute("ALTER TABLE investigation_evidence RENAME TO investigation_evidence_legacy")
        connection.execute(
            """
            CREATE TABLE investigation_evidence (
                investigation_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                incident_id TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                source TEXT NOT NULL,
                observation TEXT NOT NULL,
                value REAL,
                units TEXT,
                provenance TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (investigation_id, evidence_id),
                FOREIGN KEY (investigation_id) REFERENCES investigations (investigation_id)
            )
            """
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO investigation_evidence (
                investigation_id, evidence_id, incident_id, evidence_type, source,
                observation, value, units, provenance, payload, created_at
            )
            SELECT
                investigation_id, evidence_id, incident_id, evidence_type, source,
                observation, value, units, provenance, payload, created_at
            FROM investigation_evidence_legacy
            """
        )
        connection.execute("DROP TABLE investigation_evidence_legacy")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()
