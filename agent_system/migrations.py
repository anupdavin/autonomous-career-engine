"""Versioned, transactional, additive, and safely reversible SQLite migrations."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional


class MigrationError(RuntimeError):
    """Raised when a schema migration or rollback operation fails."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    description: str
    up: Callable[[sqlite3.Connection], None]
    down: Callable[[sqlite3.Connection], None]
    reversible: bool = True

    def compute_checksum(self) -> str:
        payload = f"{self.version}:{self.name}:{self.description}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL,
            checksum TEXT NOT NULL
        )
        """
    )


def get_current_schema_version(conn: sqlite3.Connection) -> int:
    ensure_migrations_table(conn)
    row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def get_applied_migrations(conn: sqlite3.Connection) -> List[dict[str, Any]]:
    ensure_migrations_table(conn)
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT version, name, applied_at, checksum FROM schema_migrations ORDER BY version ASC"
    ).fetchall()
    return [
        {
            "version": int(r[0]),
            "name": str(r[1]),
            "applied_at": str(r[2]),
            "checksum": str(r[3]),
        }
        for r in rows
    ]


# --- Migration 0001: Baseline Schema ---

_BASELINE_TABLES_DDL = [
    """
    CREATE TABLE IF NOT EXISTS agent_episodic_memories (
        job_id TEXT PRIMARY KEY,
        title TEXT,
        company TEXT,
        url TEXT,
        decision TEXT,
        ranker_decision TEXT DEFAULT '',
        match_score INTEGER,
        score_model_version TEXT DEFAULT 'legacy-v1',
        critic_score INTEGER,
        tailored_pitch TEXT,
        feedback_reason TEXT,
        embedding_json TEXT,
        created_at TEXT,
        lifecycle_stage TEXT DEFAULT 'SHORTLISTED',
        source_platform TEXT DEFAULT 'Live Multi-Tier Feed',
        engagement_type TEXT DEFAULT 'GLOBAL_B2B_CONTRACT',
        engagement_label TEXT DEFAULT 'Global B2B Contract',
        salary_range_display TEXT DEFAULT '$70k - $95k USD/yr',
        primary_monthly_in_hand_inr INTEGER DEFAULT 485000,
        b2b_monthly_in_hand_inr INTEGER DEFAULT 485000,
        eor_monthly_in_hand_inr INTEGER DEFAULT 395000,
        effective_tax_pct REAL DEFAULT 9.2,
        tax_summary TEXT DEFAULT '',
        resume_version_id TEXT DEFAULT 'v1.0-master-cloud-ai',
        applied_at TEXT DEFAULT '',
        next_followup_due_at TEXT DEFAULT '',
        followup_count INTEGER DEFAULT 0,
        closure_reason TEXT DEFAULT '',
        acknowledged_at TEXT DEFAULT '',
        submission_evidence_at TEXT DEFAULT '',
        submission_evidence_source TEXT DEFAULT '',
        acknowledgement_evidence_source TEXT DEFAULT '',
        work_location_status TEXT DEFAULT 'NEEDS_REVIEW',
        work_location_evidence TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS consolidated_memory_rules (
        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_type TEXT,
        rule_text TEXT UNIQUE,
        confidence REAL,
        source_count INTEGER DEFAULT 1,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS human_feedback_events (
        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        decision TEXT NOT NULL,
        reason TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kg_vertices (
        vertex_id TEXT PRIMARY KEY,
        vertex_type TEXT,
        name TEXT,
        metadata_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kg_edges (
        edge_id TEXT PRIMARY KEY,
        source_id TEXT,
        target_id TEXT,
        relation TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS application_timeline_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT,
        from_stage TEXT,
        to_stage TEXT,
        note TEXT,
        event_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_runs (
        run_id TEXT PRIMARY KEY,
        workflow TEXT NOT NULL,
        status TEXT NOT NULL,
        phase TEXT NOT NULL,
        started_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        heartbeat_at TEXT NOT NULL,
        finished_at TEXT,
        summary TEXT NOT NULL,
        error_type TEXT,
        stats_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_run_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        phase TEXT NOT NULL,
        message TEXT NOT NULL,
        details_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_run_outcomes (
        outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        source TEXT NOT NULL,
        status TEXT NOT NULL,
        collected_count INTEGER NOT NULL,
        error_type TEXT,
        details_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS resume_vault_versions (
        version_id TEXT PRIMARY KEY,
        version_tag TEXT,
        target_track TEXT,
        headline TEXT,
        executive_summary TEXT,
        bullets_json TEXT,
        linked_job_id TEXT,
        created_at TEXT,
        ats_upload_filename TEXT DEFAULT 'Meena_Kannan_Lead_Software_Engineer.pdf',
        internal_vault_path TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS resume_generation_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        version_id TEXT NOT NULL,
        company TEXT NOT NULL,
        role_title TEXT NOT NULL,
        generated_pdf_path TEXT NOT NULL,
        generated_at TEXT NOT NULL
    )
    """,
]

_BASELINE_CRM_COLUMNS = [
    ("lifecycle_stage", "TEXT DEFAULT 'SHORTLISTED'"),
    ("source_platform", "TEXT DEFAULT 'Live Multi-Tier Feed'"),
    ("engagement_type", "TEXT DEFAULT 'GLOBAL_B2B_CONTRACT'"),
    ("engagement_label", "TEXT DEFAULT 'Global B2B Contract'"),
    ("salary_range_display", "TEXT DEFAULT '$70k - $95k USD/yr'"),
    ("primary_monthly_in_hand_inr", "INTEGER DEFAULT 485000"),
    ("b2b_monthly_in_hand_inr", "INTEGER DEFAULT 485000"),
    ("eor_monthly_in_hand_inr", "INTEGER DEFAULT 395000"),
    ("effective_tax_pct", "REAL DEFAULT 9.2"),
    ("tax_summary", "TEXT DEFAULT ''"),
    ("resume_version_id", "TEXT DEFAULT 'v1.0-master-cloud-ai'"),
    ("applied_at", "TEXT DEFAULT ''"),
    ("next_followup_due_at", "TEXT DEFAULT ''"),
    ("followup_count", "INTEGER DEFAULT 0"),
    ("score_model_version", "TEXT DEFAULT 'legacy-v1'"),
    ("ranker_decision", "TEXT DEFAULT ''"),
    ("closure_reason", "TEXT DEFAULT ''"),
    ("acknowledged_at", "TEXT DEFAULT ''"),
    ("submission_evidence_at", "TEXT DEFAULT ''"),
    ("submission_evidence_source", "TEXT DEFAULT ''"),
    ("acknowledgement_evidence_source", "TEXT DEFAULT ''"),
    ("work_location_status", "TEXT DEFAULT 'NEEDS_REVIEW'"),
    ("work_location_evidence", "TEXT DEFAULT ''"),
]


def _migration_0001_up(conn: sqlite3.Connection) -> None:
    # Use individual execute statements to preserve explicit transaction boundary
    for ddl in _BASELINE_TABLES_DDL:
        conn.execute(ddl)

    # Idempotent column backfill for legacy unversioned databases
    cur = conn.cursor()
    existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(agent_episodic_memories)").fetchall()}
    for col_name, col_def in _BASELINE_CRM_COLUMNS:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE agent_episodic_memories ADD COLUMN {col_name} {col_def}")


def _migration_0001_down(conn: sqlite3.Connection) -> None:
    # Safety invariant: Never drop baseline application tables or canonical user data
    raise MigrationError(
        "Baseline application tables and canonical user data cannot be dropped. "
        "Rollback of baseline migration 0001 is prohibited to protect persisted state."
    )


# --- Migration 0002: Provenance and Retrieval Indexing ---

def _migration_0002_up(conn: sqlite3.Connection) -> None:
    # 1. Additive columns for raw listing source and collector provenance metadata
    cur = conn.cursor()
    cols = {r[1] for r in cur.execute("PRAGMA table_info(agent_episodic_memories)").fetchall()}
    if "raw_listing_source" not in cols:
        conn.execute("ALTER TABLE agent_episodic_memories ADD COLUMN raw_listing_source TEXT DEFAULT ''")
    if "source_provenance_json" not in cols:
        conn.execute("ALTER TABLE agent_episodic_memories ADD COLUMN source_provenance_json TEXT DEFAULT '{}'")

    # 2. Additive covering indexes for fast memory retrieval and lifecycle queries
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_lifecycle_location "
        "ON agent_episodic_memories (lifecycle_stage, work_location_status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_created_at "
        "ON agent_episodic_memories (created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feedback_job_id_created "
        "ON human_feedback_events (job_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_timeline_job_event "
        "ON application_timeline_events (job_id, event_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rules_type_confidence "
        "ON consolidated_memory_rules (rule_type, confidence DESC)"
    )

    # 3. Additive provenance visibility view
    conn.execute(
        """
        CREATE VIEW IF NOT EXISTS v_episodic_memory_provenance AS
        SELECT
            m.job_id,
            m.title,
            m.company,
            m.url,
            m.source_platform,
            m.raw_listing_source,
            m.source_provenance_json,
            m.lifecycle_stage,
            m.work_location_status,
            m.work_location_evidence,
            m.submission_evidence_at,
            m.submission_evidence_source,
            m.acknowledged_at,
            m.acknowledgement_evidence_source,
            m.match_score,
            m.ranker_decision,
            m.created_at,
            f.decision AS latest_feedback_decision,
            f.reason AS latest_feedback_reason,
            f.source AS latest_feedback_source,
            f.created_at AS latest_feedback_at
        FROM agent_episodic_memories m
        LEFT JOIN (
            SELECT hfe.job_id, hfe.decision, hfe.reason, hfe.source, hfe.created_at
            FROM human_feedback_events hfe
            INNER JOIN (
                SELECT job_id, MAX(feedback_id) AS max_id
                FROM human_feedback_events
                GROUP BY job_id
            ) latest ON hfe.job_id = latest.job_id AND hfe.feedback_id = latest.max_id
        ) f ON m.job_id = f.job_id
        """
    )


def _migration_0002_down(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cols = {r[1] for r in cur.execute("PRAGMA table_info(agent_episodic_memories)").fetchall()}
    has_raw = "raw_listing_source" in cols
    has_prov_json = "source_provenance_json" in cols

    # Safeguard: Refuse rollback if any row contains populated provenance values
    if has_raw or has_prov_json:
        clauses: List[str] = []
        if has_raw:
            clauses.append("NULLIF(TRIM(raw_listing_source), '') IS NOT NULL")
        if has_prov_json:
            clauses.append("(NULLIF(TRIM(source_provenance_json), '') IS NOT NULL AND source_provenance_json != '{}')")

        check_sql = f"SELECT COUNT(*) FROM agent_episodic_memories WHERE {' OR '.join(clauses)}"
        row = cur.execute(check_sql).fetchone()
        populated_count = int(row[0]) if row else 0

        if populated_count > 0:
            raise MigrationError(
                f"Rollback of migration 0002 refused: {populated_count} row(s) contain active "
                f"provenance values. Rollback aborted to prevent data loss."
            )

    # 1. Drop provenance view
    conn.execute("DROP VIEW IF EXISTS v_episodic_memory_provenance")

    # 2. Drop covering indexes
    conn.execute("DROP INDEX IF EXISTS idx_memories_lifecycle_location")
    conn.execute("DROP INDEX IF EXISTS idx_memories_created_at")
    conn.execute("DROP INDEX IF EXISTS idx_feedback_job_id_created")
    conn.execute("DROP INDEX IF EXISTS idx_timeline_job_event")
    conn.execute("DROP INDEX IF EXISTS idx_rules_type_confidence")

    # 3. Drop columns safely when proven empty
    if has_prov_json:
        conn.execute("ALTER TABLE agent_episodic_memories DROP COLUMN source_provenance_json")
    if has_raw:
        conn.execute("ALTER TABLE agent_episodic_memories DROP COLUMN raw_listing_source")


MIGRATIONS: List[Migration] = [
    Migration(
        version=1,
        name="0001_baseline_schema",
        description="Establish baseline episodic memory, CRM tracking, rules, graph, and run ledger tables.",
        up=_migration_0001_up,
        down=_migration_0001_down,
        reversible=False,
    ),
    Migration(
        version=2,
        name="0002_provenance_and_retrieval_indexing",
        description="Additive columns for raw listing provenance and source metadata, covering performance indexes, and memory provenance audit view.",
        up=_migration_0002_up,
        down=_migration_0002_down,
        reversible=True,
    ),
]


def apply_migrations(
    conn: sqlite3.Connection,
    target_version: Optional[int] = None,
) -> List[int]:
    """
    Applies pending migrations transactionally up to target_version (or latest if None).
    Returns the list of newly applied migration versions.
    """
    ensure_migrations_table(conn)
    current_version = get_current_schema_version(conn)

    max_target = target_version if target_version is not None else (MIGRATIONS[-1].version if MIGRATIONS else 0)
    pending = [m for m in MIGRATIONS if m.version > current_version and m.version <= max_target]

    if not pending:
        return []

    applied_versions: List[int] = []
    prev_isolation = conn.isolation_level
    conn.isolation_level = None  # Autocommit mode for explicit manual transactions

    try:
        for migration in pending:
            checksum = migration.compute_checksum()
            now = _now_iso()
            conn.execute("BEGIN IMMEDIATE")
            try:
                migration.up(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at, checksum) VALUES (?, ?, ?, ?)",
                    (migration.version, migration.name, now, checksum),
                )
                conn.execute("COMMIT")
                applied_versions.append(migration.version)
            except Exception as exc:
                conn.execute("ROLLBACK")
                raise MigrationError(
                    f"Failed to apply migration {migration.version} ({migration.name}): {exc}"
                ) from exc
    finally:
        conn.isolation_level = prev_isolation

    return applied_versions


def rollback_migrations(
    conn: sqlite3.Connection,
    target_version: int,
) -> List[int]:
    """
    Rolls back migrations in reverse order down to target_version transactionally.
    Returns the list of rolled back migration versions.
    """
    ensure_migrations_table(conn)
    current_version = get_current_schema_version(conn)

    if target_version >= current_version:
        return []

    migration_map = {m.version: m for m in MIGRATIONS}
    to_rollback_versions = sorted(
        [m.version for m in MIGRATIONS if m.version > target_version and m.version <= current_version],
        reverse=True,
    )

    if not to_rollback_versions:
        return []

    # Preflight check: verify all requested rollbacks are permitted before modifying database state
    for version in to_rollback_versions:
        migration = migration_map.get(version)
        if not migration:
            raise MigrationError(f"No migration definition found for version {version}")
        if not migration.reversible:
            raise MigrationError(
                f"Rollback to target {target_version} crosses non-reversible baseline migration "
                f"{migration.version} ({migration.name}). Rollback aborted before executing any changes."
            )

    rolled_back: List[int] = []
    prev_isolation = conn.isolation_level
    conn.isolation_level = None

    try:
        for version in to_rollback_versions:
            migration = migration_map[version]
            conn.execute("BEGIN IMMEDIATE")
            try:
                migration.down(conn)
                conn.execute("DELETE FROM schema_migrations WHERE version = ?", (version,))
                conn.execute("COMMIT")
                rolled_back.append(version)
            except Exception as exc:
                conn.execute("ROLLBACK")
                raise MigrationError(
                    f"Failed to rollback migration {version} ({migration.name}): {exc}"
                ) from exc
    finally:
        conn.isolation_level = prev_isolation

    return rolled_back


def ensure_schema_current(conn: sqlite3.Connection) -> int:
    """
    Ensures that all migrations are applied to the database.
    Returns the current schema version after applying any pending migrations.
    """
    apply_migrations(conn)
    return get_current_schema_version(conn)
