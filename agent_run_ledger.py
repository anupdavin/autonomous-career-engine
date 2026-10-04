"""Durable, privacy-conscious run history for long-lived agent workflows."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from config import SETTINGS


class RunAlreadyActive(RuntimeError):
    """Raised when a workflow already has an active run."""

    def __init__(self, run_id: str, phase: str) -> None:
        self.run_id = run_id
        self.phase = phase
        super().__init__(f"Run {run_id} is already active in phase {phase}")


class RunRecoveryRequired(RuntimeError):
    """Raised when a stale run needs an explicit operator recovery decision."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Run {run_id} is stale and needs operator recovery")


class AgentRunLedger:
    """Store workflow lifecycle and event metadata in the local SQLite database."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        stale_after_seconds: int = 1800,
    ) -> None:
        self.db_path = Path(db_path or SETTINGS.oracle.local_fallback_db)
        self.stale_after_seconds = max(1, int(stale_after_seconds))
        self._initialize()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._connection() as conn:
            conn.executescript(
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
                    owner_pid INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    error_type TEXT,
                    stats_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS agent_run_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at
                    ON agent_runs(started_at DESC);
                CREATE INDEX IF NOT EXISTS idx_agent_run_events_run_id
                    ON agent_run_events(run_id, event_id DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_runs_single_active
                    ON agent_runs(status) WHERE status = 'RUNNING';
                """
            )

    def _mark_expired_runs(self, conn: sqlite3.Connection, now: str) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=self.stale_after_seconds)).isoformat(
            timespec="seconds"
        )
        expired = conn.execute(
            "SELECT run_id, phase FROM agent_runs WHERE status = 'RUNNING' AND heartbeat_at < ?",
            (cutoff,),
        ).fetchall()
        if not expired:
            return
        conn.executemany(
            """
            UPDATE agent_runs
            SET status = 'STALE', phase = 'recovery_required', updated_at = ?, finished_at = ?,
                summary = 'Heartbeat expired. Inspect the process before retrying.'
            WHERE run_id = ? AND status = 'RUNNING'
            """,
            [(now, now, row["run_id"]) for row in expired],
        )
        for row in expired:
            self._insert_event(
                conn,
                row["run_id"],
                "stale_detected",
                "recovery_required",
                "warning",
                "No recent heartbeat was recorded for this run.",
                {},
                now,
            )

    @staticmethod
    def _insert_event(
        conn: sqlite3.Connection,
        run_id: str,
        event_type: str,
        phase: str,
        status: str,
        summary: str,
        details: dict[str, Any],
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO agent_run_events
                (run_id, event_type, phase, status, summary, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                event_type[:80],
                phase[:80],
                status[:24],
                summary[:500],
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                created_at,
            ),
        )

    def start_run(self, workflow: str, summary: str = "Run accepted") -> str:
        now = self._now()
        run_id = str(uuid.uuid4())
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._mark_expired_runs(conn, now)
            active = conn.execute(
                "SELECT run_id, phase FROM agent_runs WHERE status = 'RUNNING' LIMIT 1"
            ).fetchone()
            if active:
                raise RunAlreadyActive(active["run_id"], active["phase"])
            stale = conn.execute(
                "SELECT run_id FROM agent_runs WHERE status = 'STALE' ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            if stale:
                raise RunRecoveryRequired(stale["run_id"])
            conn.execute(
                """
                INSERT INTO agent_runs
                    (run_id, workflow, status, phase, started_at, updated_at, heartbeat_at,
                     owner_pid, summary)
                VALUES (?, ?, 'RUNNING', 'starting', ?, ?, ?, ?, ?)
                """,
                (run_id, workflow[:100], now, now, now, os.getpid(), summary[:500]),
            )
            self._insert_event(
                conn, run_id, "run_started", "starting", "info", summary, {}, now
            )
        return run_id

    def recover_stale_run(self, run_id: str) -> None:
        """Record an operator decision that a stale owner's process was inspected."""
        now = self._now()
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            updated = conn.execute(
                """
                UPDATE agent_runs
                SET status = 'ABANDONED', phase = 'recovered', updated_at = ?, finished_at = ?,
                    summary = 'Operator inspected the previous process and released this stale run.'
                WHERE run_id = ? AND status = 'STALE'
                """,
                (now, now, run_id),
            )
            if updated.rowcount == 0:
                raise ValueError(f"Run {run_id} is missing or is not stale")
            self._insert_event(
                conn,
                run_id,
                "stale_run_recovered",
                "recovered",
                "warning",
                "Operator inspected the previous process and released this stale run.",
                {"recovery": "operator_confirmed"},
                now,
            )

    def record_event(
        self,
        run_id: str,
        event_type: str,
        phase: str,
        summary: str,
        *,
        status: str = "info",
        details: dict[str, Any] | None = None,
        heartbeat: bool = True,
    ) -> None:
        now = self._now()
        with self._connection() as conn:
            old_heartbeat = None
            if not heartbeat:
                row = conn.execute(
                    "SELECT heartbeat_at FROM agent_runs WHERE run_id = ? AND status = 'RUNNING'",
                    (run_id,),
                ).fetchone()
                if row:
                    old_heartbeat = row["heartbeat_at"]
            updated = conn.execute(
                """
                UPDATE agent_runs
                SET phase = ?, updated_at = ?, heartbeat_at = ?, summary = ?
                WHERE run_id = ? AND status = 'RUNNING'
                """,
                (phase[:80], now, now if heartbeat else old_heartbeat, summary[:500], run_id),
            )
            if updated.rowcount == 0:
                raise ValueError(f"Run {run_id} is missing or no longer active")
            self._insert_event(
                conn,
                run_id,
                event_type,
                phase,
                status,
                summary,
                details or {},
                now,
            )

    def finish_run(
        self,
        run_id: str,
        status: str,
        summary: str,
        *,
        error_type: str | None = None,
        stats: dict[str, Any] | None = None,
    ) -> None:
        if status not in {"SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"}:
            raise ValueError(f"Unsupported terminal run status: {status}")
        now = self._now()
        phase = "completed" if status in {"SUCCEEDED", "PARTIAL"} else "stopped"
        with self._connection() as conn:
            updated = conn.execute(
                """
                UPDATE agent_runs
                SET status = ?, phase = ?, updated_at = ?, heartbeat_at = ?, finished_at = ?,
                    summary = ?, error_type = ?, stats_json = ?
                WHERE run_id = ? AND status = 'RUNNING'
                """,
                (
                    status,
                    phase,
                    now,
                    now,
                    now,
                    summary[:500],
                    error_type[:120] if error_type else None,
                    json.dumps(stats or {}, ensure_ascii=False, sort_keys=True),
                    run_id,
                ),
            )
            if updated.rowcount == 0:
                raise ValueError(f"Run {run_id} is missing or no longer active")
            self._insert_event(
                conn,
                run_id,
                "run_finished",
                phase,
                status.lower(),
                summary,
                {"error_type": error_type} if error_type else {},
                now,
            )

    @staticmethod
    def _decode_run(row: sqlite3.Row) -> dict[str, Any]:
        run = dict(row)
        try:
            run["stats"] = json.loads(run.pop("stats_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            run["stats"] = {}
            run.pop("stats_json", None)
        return run

    def recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 50))
        now = self._now()
        with self._connection() as conn:
            self._mark_expired_runs(conn, now)
            rows = conn.execute(
                "SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT ?",
                (bounded_limit,),
            ).fetchall()
        return [self._decode_run(row) for row in rows]

    def run_events(self, run_id: str, limit: int = 30) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 100))
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT event_id, event_type, phase, status, summary, details_json, created_at
                FROM agent_run_events WHERE run_id = ?
                ORDER BY event_id DESC LIMIT ?
                """,
                (run_id, bounded_limit),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            event = dict(row)
            try:
                event["details"] = json.loads(event.pop("details_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                event["details"] = {}
                event.pop("details_json", None)
            events.append(event)
        return list(reversed(events))

    def snapshot(self) -> dict[str, Any]:
        runs = self.recent_runs(limit=10)
        active = next((run for run in runs if run["status"] == "RUNNING"), None)
        latest = runs[0] if runs else None
        if active:
            status = "running"
            summary = active["summary"]
            next_actions = ["Wait for the active run or inspect its latest events."]
        elif latest and latest["status"] == "STALE":
            status = "stale"
            summary = latest["summary"]
            next_actions = [
                "Inspect the owning process. If it has stopped, record recovery with --recover-stale-run and this run ID."
            ]
        elif latest and latest["status"] == "ABANDONED":
            status = "warning"
            summary = latest["summary"]
            next_actions = ["A new discovery run can be started after stale-run recovery was recorded."]
        elif latest and latest["status"] == "FAILED":
            status = "failed"
            summary = latest["summary"]
            next_actions = ["Review the run event history, correct the cause, then retry once."]
        elif latest and latest["status"] == "PARTIAL":
            status = "warning"
            summary = latest["summary"]
            next_actions = ["Review warning events and decide whether a retry is useful."]
        elif latest:
            status = "idle"
            summary = latest["summary"]
            next_actions = ["A new discovery run can be started when needed."]
        else:
            status = "idle"
            summary = "No instrumented agent run has been recorded yet."
            next_actions = ["Start one discovery cycle to establish a run history."]
        return {
            "status": status,
            "summary": summary,
            "active_run": active,
            "latest_run": latest,
            "recent_runs": runs,
            "recent_events": self.run_events((active or latest)["run_id"]) if (active or latest) else [],
            "next_actions": next_actions,
            "artifacts": [],
        }
