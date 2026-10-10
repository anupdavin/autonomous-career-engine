"""Read-only local inspection and capability catalog for the agent system."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from adaptive_evaluation import load_ranker_quality_report
from agent_system.contracts import Artifact, Observation, ObservationStatus
from config import SETTINGS


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "agent_system" / "system_manifest.json"
FACT_REVIEW_PATH = ROOT / "candidate_fact_review.json"
GRAPH_PATH = ROOT / "architecture" / "repo_graph.json"


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read agent system manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Agent system manifest root must be an object")
    return value


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("Unsupported or missing schema_version")
    if not isinstance(manifest.get("system_name"), str) or not manifest["system_name"].strip():
        errors.append("system_name must be a non-blank string")
    if not isinstance(manifest.get("operating_model"), dict):
        errors.append("operating_model must be an object")
    else:
        operating_model = manifest["operating_model"]
        if operating_model.get("external_submission_enabled") is not False:
            errors.append("External application submission must be disabled")
        if operating_model.get("arbitrary_shell_tool_enabled") is not False:
            errors.append("Arbitrary shell execution must be disabled")

    capabilities = manifest.get("agent_capabilities")
    if not isinstance(capabilities, list):
        errors.append("agent_capabilities must be a list")
        capabilities = []
    seen_ids: set[str] = set()
    for index, capability in enumerate(capabilities):
        if not isinstance(capability, dict):
            errors.append(f"agent_capabilities[{index}] must be an object")
            continue
        capability_id = capability.get("id")
        if not isinstance(capability_id, str) or not capability_id.strip():
            errors.append(f"agent_capabilities[{index}] has no id")
        elif capability_id in seen_ids:
            errors.append(f"Duplicate capability id: {capability_id}")
        else:
            seen_ids.add(capability_id)
        if not isinstance(capability.get("description"), str) or not capability["description"].strip():
            errors.append(f"{capability_id or index} has no description")
        if not isinstance(capability.get("entrypoint"), str) or not capability["entrypoint"].strip():
            errors.append(f"{capability_id or index} has no entrypoint")
        if not isinstance(capability.get("agent_callable"), bool):
            errors.append(f"{capability_id or index} must declare agent_callable as a boolean")
        if capability.get("risk") not in {"read_only", "local_write", "external_effect"}:
            errors.append(f"{capability_id or index} has an unknown risk")
        if capability.get("agent_callable") is True and capability.get("risk") != "read_only":
            errors.append(f"Agent-callable capability {capability_id} must be read-only")
        if capability.get("risk") == "external_effect" and capability.get("agent_callable") is True:
            errors.append(f"External capability {capability_id} cannot be agent-callable")

    workflows = manifest.get("operator_workflows")
    if not isinstance(workflows, list):
        errors.append("operator_workflows must be a list")
        workflows = []
    workflow_ids: set[str] = set()
    for index, workflow in enumerate(workflows):
        if not isinstance(workflow, dict):
            errors.append(f"operator_workflows[{index}] must be an object")
            continue
        workflow_id = workflow.get("id")
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            errors.append(f"operator_workflows[{index}] has no id")
        elif workflow_id in workflow_ids:
            errors.append(f"Duplicate workflow id: {workflow_id}")
        else:
            workflow_ids.add(workflow_id)
        side_effects = workflow.get("side_effects")
        quality_gates = workflow.get("quality_gates")
        if not isinstance(side_effects, list) or any(not isinstance(item, str) for item in side_effects):
            errors.append(f"Workflow {workflow_id or index} must declare side_effects as a string list")
            side_effects = []
        if not isinstance(quality_gates, list) or any(not isinstance(item, str) for item in quality_gates):
            errors.append(f"Workflow {workflow_id or index} must declare quality_gates as a string list")
            quality_gates = []
        if side_effects and not quality_gates:
            errors.append(f"Workflow {workflow.get('id', index)} has side effects but no quality gates")
        if "external_submission" in side_effects and workflow.get("enabled") is not False:
            errors.append("External submission workflow must be explicitly disabled")
        if "external_message" in side_effects and workflow.get("enabled") is not False:
            errors.append("External messaging workflow must be explicitly disabled")
    return errors


def capability_observation(manifest_path: Path = MANIFEST_PATH) -> Observation:
    try:
        manifest = load_manifest(manifest_path)
    except ValueError as exc:
        return Observation(
            status=ObservationStatus.ERROR,
            summary=str(exc),
            next_actions=("Restore a valid system manifest before exposing agent capabilities.",),
            artifacts=(Artifact(str(manifest_path)),),
        )

    errors = validate_manifest(manifest)
    if errors:
        return Observation(
            status=ObservationStatus.ERROR,
            summary="The agent capability manifest failed validation.",
            next_actions=("Correct the manifest errors before relying on this capability catalog.",),
            artifacts=(Artifact(str(manifest_path)),),
            details={"errors": errors},
        )

    return Observation(
        status=ObservationStatus.SUCCESS,
        summary="The capability catalog is valid and contains no agent-callable external actions.",
        next_actions=("Use only listed agent capabilities. Run operator workflows through their documented gates.",),
        artifacts=(Artifact(str(manifest_path)),),
        details={
            "schema_version": manifest["schema_version"],
            "system_name": manifest["system_name"],
            "agent_capabilities": manifest["agent_capabilities"],
            "operator_workflows": manifest["operator_workflows"],
            "agent_callables_are_read_only": all(
                item["risk"] == "read_only" for item in manifest["agent_capabilities"] if item["agent_callable"]
            ),
        },
    )


def _review_summary(path: Path) -> dict[str, Any]:
    try:
        review = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"available": False, "error_type": type(exc).__name__}
    facts = review.get("facts") if isinstance(review, dict) else None
    if not isinstance(facts, dict):
        return {"available": False, "error_type": "InvalidFactReviewSchema"}
    verified = sum(
        1
        for item in facts.values()
        if isinstance(item, dict) and item.get("verified") is True and bool(str(item.get("source_ref", "")).strip())
    )
    complete = bool(str(review.get("reviewed_by", "")).strip()) and bool(
        str(review.get("reviewed_at", "")).strip()
    ) and verified == len(facts)
    return {"available": True, "required": len(facts), "verified": verified, "complete": complete}


def _database_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"available": False, "error_type": "DatabaseNotFound"}
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=3)
        conn.execute("PRAGMA query_only = ON")
        try:
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
            }
            result: dict[str, Any] = {"available": True, "run_ledger_available": "agent_runs" in tables}
            if "schema_migrations" in tables:
                schema_row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
                result["schema_version"] = schema_row[0] if schema_row else 0
            result["adaptive_feedback"] = load_ranker_quality_report(conn)
            if "agent_episodic_memories" in tables:
                columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(agent_episodic_memories)").fetchall()
                }
                required_columns = {
                    "job_id",
                    "lifecycle_stage",
                    "work_location_status",
                    "submission_evidence_at",
                    "submission_evidence_source",
                    "acknowledged_at",
                    "acknowledgement_evidence_source",
                }
                if required_columns.issubset(columns):
                    stages = {
                        str(row[0] or "UNKNOWN"): row[1]
                        for row in conn.execute(
                            "SELECT lifecycle_stage, COUNT(*) "
                            "FROM agent_episodic_memories GROUP BY lifecycle_stage"
                        ).fetchall()
                    }
                    counts = conn.execute(
                        "SELECT COUNT(*), "
                        "SUM(CASE WHEN work_location_status = 'VERIFIED' THEN 1 ELSE 0 END), "
                        "SUM(CASE WHEN lifecycle_stage = 'SHORTLISTED' "
                        "AND work_location_status = 'VERIFIED' THEN 1 ELSE 0 END), "
                        "SUM(CASE WHEN lifecycle_stage = 'APPROVED' "
                        "AND work_location_status = 'VERIFIED' THEN 1 ELSE 0 END), "
                        "SUM(CASE WHEN lifecycle_stage = 'APPLIED' THEN 1 ELSE 0 END), "
                        "SUM(CASE WHEN NULLIF(TRIM(submission_evidence_at), '') IS NOT NULL "
                        "AND NULLIF(TRIM(submission_evidence_source), '') IS NOT NULL THEN 1 ELSE 0 END), "
                        "SUM(CASE WHEN NULLIF(TRIM(acknowledged_at), '') IS NOT NULL "
                        "AND NULLIF(TRIM(acknowledgement_evidence_source), '') IS NOT NULL THEN 1 ELSE 0 END), "
                        "SUM(CASE WHEN lifecycle_stage = 'APPLIED' AND ("
                        "NULLIF(TRIM(submission_evidence_at), '') IS NULL OR "
                        "NULLIF(TRIM(submission_evidence_source), '') IS NULL) THEN 1 ELSE 0 END), "
                        "SUM(CASE WHEN NULLIF(TRIM(acknowledged_at), '') IS NOT NULL "
                        "AND NULLIF(TRIM(acknowledgement_evidence_source), '') IS NOT NULL "
                        "AND (NULLIF(TRIM(submission_evidence_at), '') IS NULL OR "
                        "NULLIF(TRIM(submission_evidence_source), '') IS NULL) THEN 1 ELSE 0 END) "
                        "FROM agent_episodic_memories"
                    ).fetchone()
                    result["job_progress"] = {
                        "available": True,
                        "stored_job_rows": counts[0] or 0,
                        "lifecycle_counts": stages,
                        "india_verified_roles": counts[1] or 0,
                        "shortlisted_india_roles": counts[2] or 0,
                        "approved_india_roles": counts[3] or 0,
                        "applied_rows": counts[4] or 0,
                        "receipt_confirmed_submissions": counts[5] or 0,
                        "acknowledged_submissions": counts[6] or 0,
                        "applied_without_receipt_evidence": counts[7] or 0,
                        "acknowledged_without_receipt_evidence": counts[8] or 0,
                    }
                else:
                    result["job_progress"] = {
                        "available": False,
                        "error_type": "JobLedgerSchemaUnavailable",
                    }
            else:
                result["job_progress"] = {"available": False, "error_type": "JobLedgerUnavailable"}
            if "agent_runs" in tables:
                result["run_counts"] = {
                    row[0]: row[1]
                    for row in conn.execute("SELECT status, COUNT(*) FROM agent_runs GROUP BY status").fetchall()
                }
                latest_run = conn.execute(
                    "SELECT run_id, workflow, status, phase, started_at, heartbeat_at "
                    "FROM agent_runs ORDER BY started_at DESC LIMIT 1"
                ).fetchone()
                if latest_run:
                    result["latest_run"] = dict(
                        zip(("run_id", "workflow", "status", "phase", "started_at", "heartbeat_at"), latest_run)
                    )
        finally:
            conn.close()
        return result
    except sqlite3.Error as exc:
        return {"available": False, "error_type": type(exc).__name__}


def _graph_summary(path: Path) -> dict[str, Any]:
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"available": False, "error_type": type(exc).__name__}
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {"available": False, "error_type": "InvalidGraphSchema"}
    return {
        "available": True,
        "nodes": len(nodes),
        "edges": len(edges),
        "parse_errors": len(graph.get("parse_errors", [])),
        "builder": graph.get("builder"),
    }


def inspect_runtime(
    root: Path = ROOT,
    *,
    database_path: Path | None = None,
    manifest_path: Path | None = None,
) -> Observation:
    manifest_file = manifest_path or root / "agent_system" / "system_manifest.json"
    facts_file = root / "candidate_fact_review.json"
    graph_file = root / "architecture" / "repo_graph.json"
    db_file = database_path or SETTINGS.oracle.local_fallback_db

    try:
        manifest = load_manifest(manifest_file)
        manifest_errors = validate_manifest(manifest)
    except ValueError as exc:
        manifest_errors = [str(exc)]
    facts = _review_summary(facts_file)
    database = _database_summary(db_file)
    graph = _graph_summary(graph_file)

    errors = list(manifest_errors)
    warnings: list[str] = []
    if not database.get("available"):
        warnings.append("Local database is unavailable for read-only runtime inspection.")
    elif not database.get("run_ledger_available"):
        warnings.append("Run ledger tables are absent. Start the instrumented workflow to create run history.")
    job_progress = database.get("job_progress", {})
    if database.get("available") and not job_progress.get("available"):
        warnings.append("Aggregate job progress is unavailable because the job ledger schema is incomplete.")
    elif job_progress.get("applied_without_receipt_evidence", 0):
        warnings.append("Some APPLIED lifecycle rows do not have saved submission receipt evidence.")
    if job_progress.get("acknowledged_without_receipt_evidence", 0):
        warnings.append("Some acknowledgement records are missing their linked submission receipt evidence.")
    adaptive_feedback = database.get("adaptive_feedback", {})
    if adaptive_feedback.get("status") == "insufficient_data":
        warnings.append("Ranking quality is not measured yet because the labeled feedback sample is below threshold.")
    elif adaptive_feedback.get("status") in {"unavailable", "migration_required"}:
        warnings.append("Ranking feedback evaluation is unavailable until its local schema is ready.")
    latest_run = database.get("latest_run") or {}
    latest_run_status = str(latest_run.get("status", "")).upper()
    if latest_run_status in {"PARTIAL", "FAILED", "STALE"}:
        warnings.append(f"The latest instrumented discovery run ended with status {latest_run_status}.")
    if not facts.get("available"):
        warnings.append("Candidate fact review metadata is unavailable or invalid.")
    elif not facts.get("complete"):
        warnings.append("Candidate fact review is incomplete. Application material preparation remains gated.")
    if not graph.get("available"):
        warnings.append("Local code graph is unavailable. Build it with tools/repo_graph.py.")
    elif graph.get("parse_errors", 0):
        warnings.append("The local code graph contains source parse errors.")

    status = ObservationStatus.ERROR if errors else ObservationStatus.WARNING if warnings else ObservationStatus.SUCCESS
    next_actions: list[str] = []
    if errors:
        next_actions.append("Fix manifest validation errors before using the agent control plane.")
    if job_progress.get("applied_without_receipt_evidence", 0):
        next_actions.append(
            "Reconcile APPLIED lifecycle rows against ATS receipt evidence before treating them as confirmed submissions."
        )
    if job_progress.get("acknowledged_without_receipt_evidence", 0):
        next_actions.append(
            "Review acknowledgement records and link each one to its submission receipt evidence."
        )
    if facts.get("available") and not facts.get("complete"):
        next_actions.append("Review each required candidate fact and add a source reference before preparing application materials.")
    if adaptive_feedback.get("next_actions"):
        next_actions.extend(str(action) for action in adaptive_feedback["next_actions"] if str(action).strip())
    if latest_run_status == "STALE":
        next_actions.append("Inspect the recorded run owner and heartbeat before recording explicit stale-run recovery.")
    elif latest_run_status in {"PARTIAL", "FAILED"}:
        next_actions.append("Review the latest discovery run's source outcomes and error details before retrying it.")
    elif latest_run_status == "RUNNING":
        next_actions.append("Monitor the active run heartbeat and source outcomes before starting another discovery cycle.")
    if job_progress.get("available"):
        if job_progress.get("shortlisted_india_roles", 0):
            next_actions.append(
                "Review the India-verified shortlist against current official listings, then approve a role only after human review."
            )
        if job_progress.get("approved_india_roles", 0) and facts.get("complete"):
            next_actions.append(
                "Prepare materials for approved, India-verified roles with the explicit one-shot preparation workflow."
            )
        elif not job_progress.get("shortlisted_india_roles", 0) and not job_progress.get("india_verified_roles", 0):
            next_actions.append("Run one instrumented discovery cycle to refresh the global-remote role set.")
        elif not job_progress.get("shortlisted_india_roles", 0) and not job_progress.get("approved_india_roles", 0):
            next_actions.append("Review current official sources for the India-verified roles and refresh stale eligibility evidence.")
    if not graph.get("available"):
        next_actions.append("Build the local Python graph, then rerun this inspection.")
    if not database.get("run_ledger_available"):
        next_actions.append("Start one instrumented discovery cycle to establish run history.")
    if not next_actions:
        next_actions.append("Continue with the reviewed operator workflow and inspect run evidence after each cycle.")

    details = {
        "manifest": {"valid": not errors, "errors": errors},
        "database": database,
        "candidate_fact_review": facts,
        "code_graph": graph,
        "warnings": warnings,
        "inspection_is_read_only": True,
        "next_actions_are_recommendations_only": True,
    }
    artifacts = tuple(
        Artifact(str(path))
        for path, exists in ((manifest_file, manifest_file.is_file()), (facts_file, facts_file.is_file()), (graph_file, graph_file.is_file()))
        if exists
    )
    summary = "Agent control-plane inspection completed."
    if errors:
        summary = "Agent control-plane inspection found manifest errors."
    elif warnings:
        summary = "Agent control-plane inspection completed with workflow readiness warnings."
    return Observation(
        status=status,
        summary=summary,
        next_actions=tuple(next_actions),
        artifacts=artifacts,
        details=details,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only control plane for the local job-search agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inspect", help="Inspect local runtime readiness without changing files or databases")
    subparsers.add_parser("capabilities", help="Print the validated agent capability and workflow catalog")
    args = parser.parse_args(argv)

    observation = inspect_runtime() if args.command == "inspect" else capability_observation()
    print(json.dumps(observation.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if observation.status == ObservationStatus.ERROR else 0


if __name__ == "__main__":
    sys.exit(main())
