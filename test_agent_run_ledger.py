import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent_run_ledger import AgentRunLedger, RunAlreadyActive, RunRecoveryRequired


class AgentRunLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "runs.sqlite3"
        self.ledger = AgentRunLedger(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_run_lifecycle_and_events_are_persisted(self) -> None:
        run_id = self.ledger.start_run("job_discovery", "Discovery accepted")
        self.ledger.record_event(
            run_id,
            "source_finished",
            "collecting",
            "Greenhouse returned one eligible listing.",
            details={"source": "Greenhouse", "eligible_count": 1},
        )

        active = self.ledger.snapshot()
        self.assertEqual(active["status"], "running")
        self.assertEqual(active["active_run"]["run_id"], run_id)
        self.assertEqual(active["recent_events"][-1]["details"]["eligible_count"], 1)

        self.ledger.finish_run(
            run_id,
            "SUCCEEDED",
            "Discovery completed.",
            stats={"collected_jobs": 1},
        )
        snapshot = self.ledger.snapshot()
        self.assertEqual(snapshot["status"], "idle")
        self.assertEqual(snapshot["latest_run"]["status"], "SUCCEEDED")
        self.assertEqual(snapshot["latest_run"]["stats"]["collected_jobs"], 1)

    def test_only_one_active_run_is_allowed(self) -> None:
        first_run_id = self.ledger.start_run("job_discovery")
        with self.assertRaises(RunAlreadyActive) as raised:
            self.ledger.start_run("job_discovery")
        self.assertEqual(raised.exception.run_id, first_run_id)

    def test_expired_heartbeat_is_marked_stale(self) -> None:
        run_id = self.ledger.start_run("job_discovery")
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE agent_runs SET heartbeat_at = ? WHERE run_id = ?",
                ("2000-01-01T00:00:00+00:00", run_id),
            )
            conn.commit()
        finally:
            conn.close()

        snapshot = self.ledger.snapshot()
        self.assertEqual(snapshot["status"], "stale")
        self.assertEqual(snapshot["latest_run"]["phase"], "recovery_required")
        self.assertEqual(snapshot["recent_events"][-1]["event_type"], "stale_detected")
        with self.assertRaises(RunRecoveryRequired) as raised:
            self.ledger.start_run("job_discovery")
        self.assertEqual(raised.exception.run_id, run_id)

        self.ledger.recover_stale_run(run_id)
        next_run_id = self.ledger.start_run("job_discovery")
        self.assertNotEqual(next_run_id, run_id)


if __name__ == "__main__":
    unittest.main()
