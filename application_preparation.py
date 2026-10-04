"""Gate application-material generation behind an explicit operator choice."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from candidate_fact_review import check_candidate_fact_readiness


class PreparationResult(TypedDict):
    status: str
    summary: str
    next_actions: list[str]
    artifacts: list[str]


def preparation_schedule_error(daemon_mode: bool, preparation_enabled: bool) -> str:
    """Prevent repeated packet generation from a periodic scheduler."""
    if daemon_mode and preparation_enabled:
        return "Run application preparation as a separate one-shot command, not in daemon mode"
    return ""


def prepare_approved_materials(
    enabled: bool,
    *,
    runner: Callable[..., list[dict[str, Any]]] | None = None,
    min_auto_score: int = 75,
    fact_review_path: Path | None = None,
) -> PreparationResult:
    """Prepare packets only when requested, returning an operator-readable result."""
    if not enabled:
        return {
            "status": "skipped",
            "summary": "Application-material preparation is disabled for this run.",
            "next_actions": [
                "Use --prepare-approved-materials only after candidate facts and each role are reviewed."
            ],
            "artifacts": [],
        }

    readiness = check_candidate_fact_readiness(fact_review_path)
    if not readiness["ready"]:
        missing = ", ".join(readiness["missing"])
        return {
            "status": "blocked",
            "summary": f"Candidate facts are not ready for application packets: {missing}.",
            "next_actions": [
                "Review candidate_fact_review.json against source material, then record the reviewer, date, and source references.",
                "Do not prepare or send a packet while any candidate fact remains unverified.",
            ],
            "artifacts": [],
        }

    if runner is None:
        from auto_applicator import run_autonomous_autopilot

        runner = run_autonomous_autopilot

    try:
        kits = runner(min_auto_score=min_auto_score)
    except Exception as exc:
        return {
            "status": "error",
            "summary": f"Application-material preparation failed: {type(exc).__name__}: {exc}",
            "next_actions": [
                "Inspect the error and any partially written files before retrying.",
                "Stop if a generated packet contains unverified candidate details.",
            ],
            "artifacts": [],
        }

    artifacts = [str(kit["pdf_path"]) for kit in kits if kit.get("pdf_path")]
    if not kits:
        return {
            "status": "warning",
            "summary": "No approved, verified roles met the preparation score threshold.",
            "next_actions": ["Review role approval, India eligibility evidence, and candidate facts."],
            "artifacts": [],
        }

    return {
        "status": "success",
        "summary": f"Prepared {len(kits)} application packet(s) for approved roles.",
        "next_actions": ["Review candidate facts and every packet before any external use."],
        "artifacts": artifacts,
    }
