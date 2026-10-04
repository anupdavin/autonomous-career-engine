import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from application_preparation import prepare_approved_materials, preparation_schedule_error
from candidate_fact_review import (
    CandidateFactReviewRequired,
    REQUIRED_FACTS,
    check_candidate_fact_readiness,
    ensure_candidate_facts_reviewed,
)


class ApplicationPreparationTests(unittest.TestCase):
    def _write_ready_manifest(self, directory: str) -> Path:
        payload = {
            "schema_version": 1,
            "reviewed_by": "candidate",
            "reviewed_at": "2026-09-28",
            "facts": {
                fact_id: {"verified": True, "source_ref": "reviewed-resume.pdf"}
                for fact_id in REQUIRED_FACTS
            },
        }
        review_path = Path(directory) / "candidate_fact_review.json"
        review_path.write_text(json.dumps(payload), encoding="utf-8")
        return review_path

    def test_daemon_mode_rejects_repeated_packet_preparation(self):
        error = preparation_schedule_error(daemon_mode=True, preparation_enabled=True)

        self.assertIn("one-shot", error)

    def test_one_shot_preparation_and_discovery_daemon_are_valid_modes(self):
        self.assertEqual(preparation_schedule_error(daemon_mode=False, preparation_enabled=True), "")
        self.assertEqual(preparation_schedule_error(daemon_mode=True, preparation_enabled=False), "")

    def test_preparation_is_skipped_without_explicit_opt_in(self):
        runner = Mock()

        result = prepare_approved_materials(False, runner=runner)

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["artifacts"], [])
        runner.assert_not_called()

    def test_preparation_is_blocked_until_all_candidate_facts_have_sources(self):
        runner = Mock()

        result = prepare_approved_materials(True, runner=runner, fact_review_path=Path("non_existent.json"))

        self.assertEqual(result["status"], "blocked")
        self.assertIn("candidate_fact_review", result["summary"])
        runner.assert_not_called()

    def test_packet_writer_guard_raises_until_review_is_complete(self):
        with self.assertRaises(CandidateFactReviewRequired):
            ensure_candidate_facts_reviewed(path=Path("non_existent.json"))

    def test_invalid_review_date_does_not_pass_readiness(self):
        payload = {
            "schema_version": 1,
            "reviewed_by": "candidate",
            "reviewed_at": "yesterday",
            "facts": {
                fact_id: {"verified": True, "source_ref": "reviewed-resume.pdf"}
                for fact_id in REQUIRED_FACTS
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            review_path = Path(directory) / "candidate_fact_review.json"
            review_path.write_text(json.dumps(payload), encoding="utf-8")

            result = check_candidate_fact_readiness(review_path)

        self.assertFalse(result["ready"])
        self.assertEqual(result["missing"], ["reviewed_at"])

    def test_opt_in_runs_only_the_preparer_and_reports_artifacts(self):
        runner = Mock(return_value=[{"job_id": "role-1", "pdf_path": "role-1/resume.pdf"}])
        with tempfile.TemporaryDirectory() as directory:
            review_path = self._write_ready_manifest(directory)

            result = prepare_approved_materials(
                True,
                runner=runner,
                min_auto_score=81,
                fact_review_path=review_path,
            )

        runner.assert_called_once_with(min_auto_score=81)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["artifacts"], ["role-1/resume.pdf"])

    def test_empty_result_is_a_warning_with_actionable_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            review_path = self._write_ready_manifest(directory)
            result = prepare_approved_materials(
                True,
                runner=Mock(return_value=[]),
                fact_review_path=review_path,
            )

        self.assertEqual(result["status"], "warning")
        self.assertIn("candidate facts", result["next_actions"][0])

    def test_failure_reports_root_cause_and_safe_retry_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            review_path = self._write_ready_manifest(directory)
            result = prepare_approved_materials(
                True,
                runner=Mock(side_effect=OSError("disk unavailable")),
                fact_review_path=review_path,
            )

        self.assertEqual(result["status"], "error")
        self.assertIn("disk unavailable", result["summary"])
        self.assertIn("partially written files", result["next_actions"][0])
        self.assertIn("Stop if", result["next_actions"][1])


if __name__ == "__main__":
    unittest.main()
