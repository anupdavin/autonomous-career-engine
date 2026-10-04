import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace

from adaptive_evaluation import evaluate_predictions, load_ranker_quality_report
from oracle_memory import OracleAIMemoryManager


class FakeVault:
    def select_best_version_for_job(self, title: str, tags: list[str]) -> str:
        return "test-resume-version"


class AdaptiveEvaluationTests(unittest.TestCase):
    def test_confusion_metrics_use_human_approval_as_the_positive_label(self) -> None:
        report = evaluate_predictions(
            [
                {"ranker_decision": "RECOMMENDED", "human_decision": "APPROVED"},
                {"ranker_decision": "RECOMMENDED", "human_decision": "REJECTED"},
                {"ranker_decision": "SKIPPED_LOW_MATCH", "human_decision": "APPROVED"},
                {"ranker_decision": "SKIPPED_LOW_MATCH", "human_decision": "REJECTED"},
            ]
        )

        self.assertEqual(report["status"], "insufficient_data")
        self.assertEqual(report["sample_count"], 4)
        self.assertEqual(report["confusion"]["false_positive"], 1)
        self.assertEqual(report["confusion"]["false_negative"], 1)
        self.assertEqual(report["metrics"]["accuracy"], 0.5)
        self.assertFalse(report["automatic_changes"])

    def test_unlabeled_or_unsupported_predictions_are_ignored(self) -> None:
        report = evaluate_predictions(
            [
                {"ranker_decision": "RECOMMENDED", "human_decision": "APPROVED"},
                {"ranker_decision": "APPROVED", "human_decision": "APPROVED"},
                {"ranker_decision": "SKIPPED_LOW_MATCH", "human_decision": "UNKNOWN"},
            ]
        )

        self.assertEqual(report["sample_count"], 1)
        self.assertEqual(report["metrics"]["precision"], 1.0)
        self.assertIsNone(report["metrics"]["specificity"])

    def test_database_report_uses_latest_human_label_and_hides_record_details(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE agent_episodic_memories (job_id TEXT, ranker_decision TEXT)")
        conn.execute(
            "CREATE TABLE human_feedback_events (feedback_id INTEGER, job_id TEXT, decision TEXT)"
        )
        conn.execute("INSERT INTO agent_episodic_memories VALUES ('job-a', 'RECOMMENDED')")
        conn.executemany(
            "INSERT INTO human_feedback_events VALUES (?, ?, ?)",
            [(1, "job-a", "REJECTED"), (2, "job-a", "APPROVED")],
        )

        report = load_ranker_quality_report(conn)

        self.assertEqual(report["reviewed_examples"], 1)
        self.assertEqual(report["sample_count"], 1)
        self.assertEqual(report["confusion"]["true_positive"], 1)
        self.assertNotIn("job-a", str(report))
        conn.close()

    def test_database_report_requests_migration_when_prediction_column_is_missing(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE agent_episodic_memories (job_id TEXT)")
        conn.execute(
            "CREATE TABLE human_feedback_events (feedback_id INTEGER, job_id TEXT, decision TEXT)"
        )
        conn.execute("INSERT INTO agent_episodic_memories VALUES ('job-a')")
        conn.execute("INSERT INTO human_feedback_events VALUES (1, 'job-a', 'APPROVED')")

        report = load_ranker_quality_report(conn)

        self.assertEqual(report["status"], "migration_required")
        self.assertEqual(report["reviewed_examples"], 1)
        self.assertEqual(report["sample_count"], 0)
        conn.close()

    def test_human_feedback_preserves_the_original_ranker_snapshot(self) -> None:
        memory = OracleAIMemoryManager.__new__(OracleAIMemoryManager)
        memory.profile = {"dealbreakers": [], "knowledge_graph": {}}
        memory.config = SimpleNamespace(local_fallback_db=Path("unused.sqlite3"))
        memory.oracle_conn = None
        memory.local_conn = sqlite3.connect(":memory:")
        memory.local_conn.row_factory = sqlite3.Row
        memory._init_storage()
        memory._backfill_crm_columns()
        memory.vault = FakeVault()
        try:
            memory.save_episodic_memory(
                job_id="test-job",
                title="Senior Backend Engineer",
                company="Example Company",
                url="https://example.invalid/jobs/1",
                decision="RECOMMENDED",
                match_score=82,
                critic_score=0,
                tailored_pitch="Test draft",
                feedback_reason="Profile evidence overlap for the test role.",
                raw_text="Senior backend engineer role with remote India eligibility.",
                work_location_status="VERIFIED",
            )
            memory.consolidate_user_feedback(
                "test-job", "APPROVED", "Strong fit for backend platform ownership."
            )
            memory.save_episodic_memory(
                job_id="test-job",
                title="Senior Backend Engineer",
                company="Example Company",
                url="https://example.invalid/jobs/1",
                decision="SKIPPED_LOW_MATCH",
                match_score=20,
                critic_score=0,
                tailored_pitch="Updated test draft",
                feedback_reason="A later rescore was lower.",
                raw_text="Senior backend engineer role with remote India eligibility.",
                work_location_status="VERIFIED",
            )

            row = memory.local_conn.execute(
                "SELECT decision, ranker_decision, match_score FROM agent_episodic_memories WHERE job_id = ?",
                ("test-job",),
            ).fetchone()
            report = load_ranker_quality_report(memory.local_conn)

            self.assertEqual(row["decision"], "APPROVED")
            self.assertEqual(row["ranker_decision"], "RECOMMENDED")
            self.assertEqual(row["match_score"], 82)
            self.assertEqual(report["confusion"]["true_positive"], 1)
            self.assertEqual(
                memory.retrieve_similar_episodic_memories("backend platform engineer", top_k=1)[0]["decision"],
                "APPROVED",
            )
        finally:
            memory.local_conn.close()


if __name__ == "__main__":
    unittest.main()
