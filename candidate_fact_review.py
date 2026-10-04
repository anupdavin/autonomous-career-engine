"""Track explicit review of candidate facts before preparing application packets."""

import json
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_REVIEW_PATH = Path(__file__).with_name("candidate_fact_review.json")
REQUIRED_FACTS = (
    "identity_and_contact",
    "employment_history_and_dates",
    "education_or_equivalent_experience",
    "current_location_and_india_work_authorization",
    "resume_role_and_technology_claims",
)


class CandidateFactReviewRequired(RuntimeError):
    """Raised when material generation is attempted before candidate review."""


def check_candidate_fact_readiness(path: Path | None = None) -> dict[str, Any]:
    """Return readiness only when each required fact has a reviewed source reference."""
    review_path = path or DEFAULT_REVIEW_PATH
    try:
        payload = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"ready": False, "missing": ["candidate_fact_review.json"]}

    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return {"ready": False, "missing": ["valid_schema"]}

    missing: list[str] = []
    reviewer = payload.get("reviewed_by", "")
    if not isinstance(reviewer, str) or not reviewer.strip():
        missing.append("reviewed_by")
    reviewed_at = payload.get("reviewed_at", "")
    if not isinstance(reviewed_at, str):
        reviewed_at = ""
    try:
        date.fromisoformat(reviewed_at)
    except ValueError:
        missing.append("reviewed_at")

    facts = payload.get("facts")
    if not isinstance(facts, dict):
        facts = {}
    for fact_id in REQUIRED_FACTS:
        record = facts.get(fact_id)
        if not isinstance(record, dict) or record.get("verified") is not True:
            missing.append(fact_id)
            continue
        source_ref = record.get("source_ref", "")
        if not isinstance(source_ref, str) or not source_ref.strip():
            missing.append(f"{fact_id}.source_ref")

    return {"ready": not missing, "missing": missing}


def ensure_candidate_facts_reviewed(path: Path | None = None) -> None:
    """Stop packet generation when candidate facts lack a reviewed source record."""
    result = check_candidate_fact_readiness(path)
    if not result["ready"]:
        missing = ", ".join(result["missing"])
        raise CandidateFactReviewRequired(f"Candidate fact review is incomplete: {missing}")
