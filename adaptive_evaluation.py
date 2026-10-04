"""Evaluate ranking snapshots against the latest explicit human decisions."""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable


def evaluate_predictions(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    confusion = {"true_positive": 0, "false_positive": 0, "true_negative": 0, "false_negative": 0}
    sample_count = 0
    for row in rows:
        predicted = row.get("ranker_decision") == "RECOMMENDED"
        actual = row.get("human_decision") == "APPROVED"
        ranker_label = row.get("ranker_decision")
        human_label = row.get("human_decision")
        if ranker_label not in {"RECOMMENDED", "SKIPPED_LOW_MATCH"}:
            continue
        if human_label not in {"APPROVED", "REJECTED"}:
            continue
        sample_count += 1
        if predicted and actual:
            confusion["true_positive"] += 1
        elif predicted:
            confusion["false_positive"] += 1
        elif actual:
            confusion["false_negative"] += 1
        else:
            confusion["true_negative"] += 1

    tp = confusion["true_positive"]
    fp = confusion["false_positive"]
    tn = confusion["true_negative"]
    fn = confusion["false_negative"]
    metrics = {
        "accuracy": _ratio(tp + tn, sample_count),
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
        "specificity": _ratio(tn, tn + fp),
    }
    status = "measured" if sample_count >= 10 else "insufficient_data"
    next_actions = (
        ["Review false positives and false negatives before proposing any ranking change."]
        if status == "measured"
        else ["Collect at least 10 explicit human decisions before interpreting ranking metrics."]
    )
    return {
        "status": status,
        "sample_count": sample_count,
        "confusion": confusion,
        "metrics": metrics,
        "interpretation": "Approval means the person accepted the role for review. It does not measure hiring outcome or recruiter response.",
        "automatic_changes": False,
        "next_actions": next_actions,
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def load_ranker_quality_report(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return aggregate quality counts without exposing job or candidate details."""
    previous_row_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        if not {"agent_episodic_memories", "human_feedback_events"}.issubset(tables):
            return {
                "status": "unavailable",
                "sample_count": 0,
                "reviewed_examples": 0,
                "missing_prediction_snapshots": 0,
                "confusion": {
                    "true_positive": 0,
                    "false_positive": 0,
                    "true_negative": 0,
                    "false_negative": 0,
                },
                "metrics": {"accuracy": None, "precision": None, "recall": None, "specificity": None},
                "interpretation": "The local job database is not initialized.",
                "automatic_changes": False,
                "next_actions": ["Open the dashboard state once to initialize the local tracker."],
            }
        reviewed_count = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT job_id, MAX(feedback_id)
                FROM human_feedback_events
                WHERE decision IN ('APPROVED', 'REJECTED')
                GROUP BY job_id
            )
            """
        ).fetchone()[0]
        job_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(agent_episodic_memories)").fetchall()
        }
        if "ranker_decision" not in job_columns:
            return {
                "status": "migration_required",
                "sample_count": 0,
                "reviewed_examples": int(reviewed_count),
                "missing_prediction_snapshots": int(reviewed_count),
                "confusion": {
                    "true_positive": 0,
                    "false_positive": 0,
                    "true_negative": 0,
                    "false_negative": 0,
                },
                "metrics": {"accuracy": None, "precision": None, "recall": None, "specificity": None},
                "interpretation": "The original ranker snapshot column has not been initialized by the updated application.",
                "automatic_changes": False,
                "next_actions": ["Open the updated dashboard to apply the local schema migration."],
            }
        rows = conn.execute(
            """
            SELECT job.ranker_decision, feedback.decision AS human_decision
            FROM agent_episodic_memories AS job
            JOIN (
                SELECT job_id, MAX(feedback_id) AS latest_feedback_id
                FROM human_feedback_events
                WHERE decision IN ('APPROVED', 'REJECTED')
                GROUP BY job_id
            ) AS latest ON latest.job_id = job.job_id
            JOIN human_feedback_events AS feedback
              ON feedback.feedback_id = latest.latest_feedback_id
            """
        ).fetchall()
    finally:
        conn.row_factory = previous_row_factory
    report = evaluate_predictions(dict(row) for row in rows)
    report["reviewed_examples"] = int(reviewed_count)
    report["missing_prediction_snapshots"] = max(0, int(reviewed_count) - report["sample_count"])
    return report
