import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent_system.control_plane import (
    capability_observation,
    inspect_runtime,
    load_manifest,
    validate_manifest,
)
from agent_system.contracts import Artifact, Observation, ObservationStatus


class ObservationContractTests(unittest.TestCase):
    def test_serialization_has_stable_fields(self):
        observation = Observation(
            status=ObservationStatus.SUCCESS,
            summary="Inspection complete.",
            next_actions=("Review the report.",),
            artifacts=(Artifact("architecture/repo_graph.json", identifier="local-graph"),),
            details={"read_only": True},
        )

        self.assertEqual(
            set(observation.to_dict()),
            {"status", "summary", "next_actions", "artifacts", "details"},
        )
        self.assertEqual(observation.to_dict()["status"], "success")
        self.assertEqual(observation.to_dict()["artifacts"][0]["id"], "local-graph")

    def test_blank_summary_is_rejected(self):
        with self.assertRaises(ValueError):
            Observation(status=ObservationStatus.ERROR, summary=" ")


class ManifestTests(unittest.TestCase):
    def test_checked_in_manifest_is_valid(self):
        manifest = load_manifest()
        self.assertEqual(validate_manifest(manifest), [])
        self.assertEqual(capability_observation().status, ObservationStatus.SUCCESS)

    def test_manifest_rejects_agent_callable_write_capability(self):
        manifest = {
            "schema_version": 1,
            "system_name": "test",
            "operating_model": {
                "external_submission_enabled": False,
                "arbitrary_shell_tool_enabled": False,
            },
            "agent_capabilities": [
                {"id": "write", "risk": "local_write", "agent_callable": True}
            ],
            "operator_workflows": [],
        }

        self.assertIn(
            "Agent-callable capability write must be read-only",
            validate_manifest(manifest),
        )

    def test_manifest_rejects_enabled_external_submission(self):
        manifest = {
            "schema_version": 1,
            "system_name": "test",
            "operating_model": {
                "external_submission_enabled": False,
                "arbitrary_shell_tool_enabled": False,
            },
            "agent_capabilities": [],
            "operator_workflows": [
                {
                    "id": "submit",
                    "enabled": True,
                    "side_effects": ["external_submission"],
                    "quality_gates": ["approval"],
                }
            ],
        }

        self.assertIn(
            "External submission workflow must be explicitly disabled",
            validate_manifest(manifest),
        )


class RuntimeInspectionTests(unittest.TestCase):
    def test_inspection_is_read_only_and_reports_gate_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agent_system").mkdir()
            (root / "architecture").mkdir()
            manifest = load_manifest()
            manifest_path = root / "agent_system" / "system_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (root / "candidate_fact_review.json").write_text(
                json.dumps(
                    {
                        "reviewed_by": "candidate",
                        "reviewed_at": "2026-09-28",
                        "facts": {
                            "identity": {"verified": True, "source_ref": "resume.pdf"},
                            "employment": {"verified": False, "source_ref": ""},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "architecture" / "repo_graph.json").write_text(
                json.dumps({"nodes": [{"id": "one"}], "edges": [], "parse_errors": []}),
                encoding="utf-8",
            )
            database_path = root / "agent.db"
            conn = sqlite3.connect(database_path)
            try:
                conn.execute(
                    "CREATE TABLE agent_runs (run_id TEXT, workflow TEXT, status TEXT, phase TEXT, "
                    "started_at TEXT, heartbeat_at TEXT)"
                )
                conn.execute(
                    "INSERT INTO agent_runs VALUES (?, ?, ?, ?, ?, ?)",
                    ("run-1", "discovery", "SUCCEEDED", "completed", "2026-09-28", "2026-09-28"),
                )
                conn.commit()
            finally:
                conn.close()

            observation = inspect_runtime(root, database_path=database_path, manifest_path=manifest_path)

        payload = observation.to_dict()
        self.assertEqual(payload["status"], "warning")
        self.assertTrue(payload["details"]["inspection_is_read_only"])
        self.assertEqual(payload["details"]["candidate_fact_review"]["verified"], 1)
        self.assertFalse(payload["details"]["candidate_fact_review"]["complete"])
        self.assertEqual(payload["details"]["database"]["run_counts"], {"SUCCEEDED": 1})
        self.assertEqual(payload["details"]["code_graph"]["nodes"], 1)


if __name__ == "__main__":
    unittest.main()
