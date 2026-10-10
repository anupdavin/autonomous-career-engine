"""Unit tests for SQLite versioned migrations and memory provenance using file-backed fixtures."""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent_system.migrations import (
    MIGRATIONS,
    Migration,
    MigrationError,
    apply_migrations,
    ensure_schema_current,
    get_applied_migrations,
    get_current_schema_version,
    rollback_migrations,
)
from oracle_memory import OracleAIMemoryManager


class TestSqliteMigrationsFileBacked(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_file.close()
        self.fixture_path = Path(self.temp_file.name)
        self.conn = sqlite3.connect(str(self.fixture_path))
        self.conn.row_factory = sqlite3.Row

    def tearDown(self) -> None:
        self.conn.close()
        if self.fixture_path.exists():
            try:
                os.remove(self.fixture_path)
            except OSError:
                pass

    def test_legacy_unversioned_database_adoption_and_rollback_refusal(self) -> None:
        # 1. Establish an unversioned legacy schema with existing synthetic rows
        self.conn.execute(
            """
            CREATE TABLE agent_episodic_memories (
                job_id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                url TEXT,
                decision TEXT,
                match_score INTEGER,
                critic_score INTEGER,
                tailored_pitch TEXT,
                feedback_reason TEXT,
                embedding_json TEXT,
                created_at TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE human_feedback_events (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        synthetic_legacy_jobs = [
            (
                "legacy_job_01",
                "Senior Java Engineer",
                "Legacy Partner A",
                "https://example.com/job/01",
                "RECOMMENDED",
                88,
                0,
                "Tailored pitch 01",
                "Strong profile overlap",
                json.dumps([0.1] * 64),
                "2026-10-01T10:00:00Z",
            ),
            (
                "legacy_job_02",
                "Lead Cloud Architect",
                "Legacy Partner B",
                "https://example.com/job/02",
                "RECOMMENDED",
                91,
                0,
                "Tailored pitch 02",
                "Strong cloud overlap",
                json.dumps([0.2] * 64),
                "2026-10-01T11:00:00Z",
            ),
        ]
        self.conn.executemany(
            """
            INSERT INTO agent_episodic_memories
            (job_id, title, company, url, decision, match_score, critic_score, tailored_pitch, feedback_reason, embedding_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            synthetic_legacy_jobs,
        )
        self.conn.execute(
            """
            INSERT INTO human_feedback_events (job_id, decision, reason, source, created_at)
            VALUES ('legacy_job_01', 'APPROVED', 'Verified strong Java alignment', 'human_review', '2026-10-01T12:00:00Z')
            """
        )
        self.conn.commit()

        # Initial unversioned state
        self.assertEqual(get_current_schema_version(self.conn), 0)

        # 2. Idempotent adoption on legacy unversioned database
        version = ensure_schema_current(self.conn)
        self.assertEqual(version, 2)

        cur = self.conn.cursor()
        job_count = cur.execute("SELECT COUNT(*) FROM agent_episodic_memories").fetchone()[0]
        feedback_count = cur.execute("SELECT COUNT(*) FROM human_feedback_events").fetchone()[0]
        self.assertEqual(job_count, 2)
        self.assertEqual(feedback_count, 1)

        cols = {r[1] for r in cur.execute("PRAGMA table_info(agent_episodic_memories)").fetchall()}
        self.assertIn("lifecycle_stage", cols)
        self.assertIn("raw_listing_source", cols)
        self.assertIn("source_provenance_json", cols)

        # 3. Populate provenance values on existing rows
        cur.execute(
            """
            UPDATE agent_episodic_memories
            SET raw_listing_source = 'https://example.com/feed/legacy_01',
                source_provenance_json = '{"collector": "legacy_feed", "batch": "b1"}'
            WHERE job_id = 'legacy_job_01'
            """
        )
        cur.execute(
            """
            UPDATE agent_episodic_memories
            SET raw_listing_source = 'https://example.com/feed/legacy_02',
                source_provenance_json = '{"collector": "legacy_feed", "batch": "b2"}'
            WHERE job_id = 'legacy_job_02'
            """
        )
        self.conn.commit()

        # Check provenance population count
        populated_count = cur.execute(
            """
            SELECT COUNT(*) FROM agent_episodic_memories
            WHERE NULLIF(TRIM(raw_listing_source), '') IS NOT NULL
              AND NULLIF(TRIM(source_provenance_json), '') IS NOT NULL
              AND source_provenance_json != '{}'
            """
        ).fetchone()[0]
        self.assertEqual(populated_count, 2)

        # 4. Attempt rollback: Must refuse rollback when provenance columns contain active values
        with self.assertRaises(MigrationError):
            rollback_migrations(self.conn, target_version=1)

        # 5. Assert refusal leaves schema version, row counts, and provenance values intact
        self.assertEqual(get_current_schema_version(self.conn), 2)
        job_count_after_refusal = cur.execute("SELECT COUNT(*) FROM agent_episodic_memories").fetchone()[0]
        feedback_count_after_refusal = cur.execute("SELECT COUNT(*) FROM human_feedback_events").fetchone()[0]
        self.assertEqual(job_count_after_refusal, 2)
        self.assertEqual(feedback_count_after_refusal, 1)

        populated_after_refusal = cur.execute(
            """
            SELECT COUNT(*) FROM agent_episodic_memories
            WHERE NULLIF(TRIM(raw_listing_source), '') IS NOT NULL
              AND NULLIF(TRIM(source_provenance_json), '') IS NOT NULL
              AND source_provenance_json != '{}'
            """
        ).fetchone()[0]
        self.assertEqual(populated_after_refusal, 2)

        # Provenance view must remain intact and queryable
        view_count = cur.execute("SELECT COUNT(*) FROM v_episodic_memory_provenance").fetchone()[0]
        self.assertEqual(view_count, 2)

        # 6. Attempt rollback of baseline schema: Must be refused to protect application tables
        with self.assertRaises(MigrationError):
            rollback_migrations(self.conn, target_version=0)
        self.assertEqual(get_current_schema_version(self.conn), 2)

    def test_preflight_refusal_when_crossing_baseline_from_v2(self) -> None:
        # Start at version 2 on a temporary file-backed SQLite database
        ensure_schema_current(self.conn)
        self.assertEqual(get_current_schema_version(self.conn), 2)

        cur = self.conn.cursor()
        # Seed synthetic job with empty provenance columns
        cur.execute(
            """
            INSERT INTO agent_episodic_memories
            (job_id, title, company, url, decision, match_score, critic_score, tailored_pitch,
             feedback_reason, embedding_json, created_at, raw_listing_source, source_provenance_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '{}')
            """,
            (
                "syn_preflight_01",
                "Senior Staff Engineer",
                "Acme Global",
                "https://example.com/job/preflight",
                "RECOMMENDED",
                89,
                0,
                "Preflight pitch",
                "Strong fit",
                json.dumps([0.1] * 64),
                "2026-10-04T12:00:00Z",
            ),
        )
        self.conn.commit()

        initial_count = cur.execute("SELECT COUNT(*) FROM agent_episodic_memories").fetchone()[0]
        self.assertEqual(initial_count, 1)

        # Preflight verification: calling rollback down to target 0 from version 2
        # must be refused before changing anything, even though provenance is empty
        with self.assertRaises(MigrationError) as ctx:
            rollback_migrations(self.conn, target_version=0)
        self.assertIn("crosses non-reversible baseline migration", str(ctx.exception))

        # Assert schema version remains at 2 (not rolled back to 1 or 0)
        self.assertEqual(get_current_schema_version(self.conn), 2)

        # Assert columns remain unchanged
        cols = {r[1] for r in cur.execute("PRAGMA table_info(agent_episodic_memories)").fetchall()}
        self.assertIn("raw_listing_source", cols)
        self.assertIn("source_provenance_json", cols)

        # Assert indexes remain unchanged
        indexes = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        self.assertIn("idx_memories_lifecycle_location", indexes)
        self.assertIn("idx_memories_created_at", indexes)
        self.assertIn("idx_feedback_job_id_created", indexes)

        # Assert view remains unchanged
        views = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()}
        self.assertIn("v_episodic_memory_provenance", views)

        # Assert row count remains unchanged
        count_after = cur.execute("SELECT COUNT(*) FROM agent_episodic_memories").fetchone()[0]
        self.assertEqual(count_after, 1)

    def test_clean_migration_lifecycle(self) -> None:
        self.assertEqual(get_current_schema_version(self.conn), 0)

        applied_v1 = apply_migrations(self.conn, target_version=1)
        self.assertEqual(applied_v1, [1])
        self.assertEqual(get_current_schema_version(self.conn), 1)

        applied_v2 = apply_migrations(self.conn, target_version=2)
        self.assertEqual(applied_v2, [2])
        self.assertEqual(get_current_schema_version(self.conn), 2)

        history = get_applied_migrations(self.conn)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["version"], 1)
        self.assertEqual(history[1]["version"], 2)

    def test_atomic_transaction_rollback(self) -> None:
        apply_migrations(self.conn, target_version=2)
        self.assertEqual(get_current_schema_version(self.conn), 2)

        def failing_up(conn: sqlite3.Connection) -> None:
            conn.execute("CREATE TABLE partial_step (id INT)")
            conn.execute("SYNTAX ERROR SIMULATED")

        faulty = Migration(
            version=99,
            name="0099_faulty_test",
            description="Faulty test migration",
            up=failing_up,
            down=lambda conn: None,
        )
        MIGRATIONS.append(faulty)
        try:
            with self.assertRaises(MigrationError):
                apply_migrations(self.conn, target_version=99)

            self.assertEqual(get_current_schema_version(self.conn), 2)
            tables = {r[0] for r in self.conn.cursor().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            self.assertNotIn("partial_step", tables)
        finally:
            MIGRATIONS.remove(faulty)

    def test_oracle_memory_manager_provenance_integration(self) -> None:
        manager = OracleAIMemoryManager(local_conn=self.conn)
        self.assertEqual(get_current_schema_version(self.conn), 2)

        manager.save_episodic_memory(
            job_id="prov_test_01",
            title="Principal Cloud Architect",
            company="Global Enterprise",
            url="https://example.com/job/cloud",
            decision="RECOMMENDED",
            match_score=92,
            critic_score=0,
            tailored_pitch="Senior cloud architect pitch",
            feedback_reason="Strong distributed systems match",
            raw_text="AWS Kubernetes Java 21 Kafka architecture remote from India",
            source_platform="Synthetic Job Board",
            work_location_status="VERIFIED",
            work_location_evidence="Official notice: Worldwide remote eligible",
            raw_listing_source="https://example.com/listings/cloud-92",
            source_provenance_json=json.dumps({"feed_id": "global_cloud", "batch": 101}),
        )

        manager.consolidate_user_feedback(
            job_id="prov_test_01",
            decision="APPROVED",
            reason="Confirmed full alignment with cloud and kafka skills",
            source="operator_portal",
        )

        # Retrieval check
        memories = manager.retrieve_similar_episodic_memories("AWS Kubernetes Java Kafka", top_k=1)
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["job_id"], "prov_test_01")
        self.assertEqual(memories[0]["decision"], "APPROVED")
        self.assertEqual(memories[0]["feedback_source"], "operator_portal")
        self.assertEqual(memories[0]["work_location_status"], "VERIFIED")
        self.assertIn("feedback_created_at", memories[0])

        # Provenance audit check
        prov = manager.get_memory_provenance("prov_test_01")
        self.assertIsNotNone(prov)
        self.assertEqual(prov["job_id"], "prov_test_01")
        self.assertEqual(prov["raw_listing_source"], "https://example.com/listings/cloud-92")
        self.assertEqual(prov["source_provenance"]["feed_id"], "global_cloud")
        self.assertEqual(len(prov["feedback_history"]), 1)
        self.assertEqual(prov["feedback_history"][0]["decision"], "APPROVED")

        # Provenance records list check
        records = manager.list_provenance_records(limit=5)
        self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
