import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Route

from adaptive_evaluation import load_ranker_quality_report
from agent_run_ledger import AgentRunLedger, RunAlreadyActive, RunRecoveryRequired
from agent_system.control_plane import capability_observation, inspect_runtime
from agent_system.contracts import ObservationStatus
from config import BASE_DIR, SETTINGS
from guardrails import assert_no_emdashes, sanitize_no_emdashes
from eligibility import global_remote_evidence
from oracle_memory import OracleAIMemoryManager
from scheduler_24_7 import run_discovery_cycle
from tax_salary_engine import FX_TO_INR, calculate_b2b_vs_employee_takehome

UI_FILE = Path(__file__).resolve().parent / "dashboard_ui.html"

CURATED_TABLES: Dict[str, Dict[str, Any]] = {
    "agent_episodic_memories": {
        "display_name": "Tracked Opportunities and Episodic Memory",
        "description": "Curated job records with lifecycle stage, eligibility, and operational timestamps.",
        "columns": [
            "job_id",
            "title",
            "company",
            "lifecycle_stage",
            "work_location_status",
            "engagement_type",
            "source_platform",
            "match_score",
            "created_at",
            "applied_at",
            "submission_evidence_at",
            "acknowledged_at",
            "next_followup_due_at",
        ],
        "default_order_by": "created_at DESC",
    },
    "application_timeline_events": {
        "display_name": "Application Timeline Events",
        "description": "Auditable log of role stage transitions and state changes.",
        "columns": [
            "event_id",
            "job_id",
            "from_stage",
            "to_stage",
            "event_at",
        ],
        "default_order_by": "event_id DESC",
    },
    "agent_runs": {
        "display_name": "Agent Execution Runs",
        "description": "Operational record of discovery and workflow execution phases.",
        "columns": [
            "run_id",
            "workflow",
            "status",
            "phase",
            "started_at",
            "updated_at",
            "finished_at",
        ],
        "default_order_by": "started_at DESC",
    },
    "schema_migrations": {
        "display_name": "Applied Schema Migrations",
        "description": "Versioned database schema migration history.",
        "columns": [
            "version",
            "name",
            "applied_at",
        ],
        "default_order_by": "version ASC",
    },
}

URL_REDACTION_PATTERN = re.compile(
    r"https?://[^\s<>\"']+|www\.[^\s<>\"']+|[a-zA-Z0-9.-]+\.trycloudflare\.com|[a-zA-Z0-9.-]+\.serveo\.net|[a-zA-Z0-9.-]+\.localtunnel\.me",
    re.IGNORECASE,
)
EMAIL_REDACTION_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def sanitize_curated_value(val: Any) -> Any:
    if isinstance(val, str):
        cleaned = URL_REDACTION_PATTERN.sub("[REDACTED_URL]", val)
        cleaned = EMAIL_REDACTION_PATTERN.sub("[REDACTED_EMAIL]", cleaned)
        return sanitize_no_emdashes(cleaned)
    return val


def resolve_curated_status_filter_column(
    table_name: str,
    status_value: str,
    available_cols: List[str],
) -> str:
    """
    Resolve the target column for status filtering.
    For agent_episodic_memories:
      - SHORTLISTED, APPROVED, APPLIED, INTERVIEW, OFFER, DEAD_ZONE filter lifecycle_stage.
      - VERIFIED, NEEDS_REVIEW, INELIGIBLE filter work_location_status.
    For agent_runs:
      - Filters status.
    For application_timeline_events:
      - Filters to_stage.
    """
    val = status_value.strip().upper()
    if table_name == "agent_episodic_memories":
        lifecycle_stages = {
            "SHORTLISTED",
            "APPROVED",
            "APPLIED",
            "INTERVIEW",
            "OFFER",
            "DEAD_ZONE",
        }
        location_statuses = {"VERIFIED", "NEEDS_REVIEW", "INELIGIBLE"}
        if val in lifecycle_stages and "lifecycle_stage" in available_cols:
            return "lifecycle_stage"
        if val in location_statuses and "work_location_status" in available_cols:
            return "work_location_status"
        return "lifecycle_stage" if "lifecycle_stage" in available_cols else ""

    if table_name == "agent_runs" and "status" in available_cols:
        return "status"

    if table_name == "application_timeline_events" and "to_stage" in available_cols:
        return "to_stage"

    if "status" in available_cols:
        return "status"
    if "to_stage" in available_cols:
        return "to_stage"
    if "lifecycle_stage" in available_cols:
        return "lifecycle_stage"
    return ""


def build_state_payload() -> Dict[str, Any]:
    memory = OracleAIMemoryManager()
    jobs = memory.get_all_crm_jobs()
    applied_without_receipt = sum(
        1
        for job in jobs
        if job.get("lifecycle_stage") == "APPLIED"
        and not (job.get("submission_evidence_at") and job.get("submission_evidence_source"))
    )
    for job in jobs:
        if (
            job.get("lifecycle_stage") == "APPLIED"
            and not (job.get("submission_evidence_at") and job.get("submission_evidence_source"))
        ):
            job["lifecycle_stage"] = "SUBMITTED_UNVERIFIED"
    existing_ids = {j.get("job_id") for j in jobs}
    existing_urls = {j.get("url") for j in jobs}

    # Merge Easy-Apply Direct Submissions (Ashby, Lever, Workable, BreezyHR, Recruitee)
    easy_results_path = Path(__file__).parent / "easy_apply_submission_results.json"
    if easy_results_path.exists():
        try:
            easy_items = json.loads(easy_results_path.read_text(encoding="utf-8"))
            for item in easy_items:
                jid = item.get("job_id") or f"easy_{item.get('platform', 'ats').lower()}_{item.get('index', 0)}"
                if jid not in existing_ids and item.get("url") not in existing_urls:
                    status_str = item.get("status", "SUBMIT_CLICKED")
                    proof_ref = str(item.get("proof", "")).strip()
                    proof_path = Path(__file__).parent / proof_ref if proof_ref else None
                    has_receipt = (
                        status_str == "CONFIRMED_SUBMITTED"
                        and proof_path is not None
                        and proof_path.is_file()
                    )
                    submit_attempted = status_str in (
                        "SUBMIT_CLICKED",
                        "SUBMITTED_UNVERIFIED",
                        "CONFIRMED_SUBMITTED",
                    )
                    lifecycle_stage = (
                        "APPLIED"
                        if has_receipt
                        else "SUBMITTED_UNVERIFIED"
                        if submit_attempted
                        else "SHORTLISTED"
                    )
                    jobs.insert(0, {
                        "job_id": jid,
                        "title": sanitize_no_emdashes(item.get("title", "Senior Java / Backend Engineer")),
                        "company": sanitize_no_emdashes(item.get("company", "Global Remote Partner")),
                        "location": "100% Remote (India / Global B2B)",
                        "platform": f"{item.get('platform', 'Direct')} Easy-Apply",
                        "url": item.get("url", ""),
                        "match_score": 96,
                        "lifecycle_stage": lifecycle_stage,
                        "work_location_status": item.get("work_location_status") or "NEEDS_REVIEW",
                        "work_location_evidence": item.get("work_location_evidence", ""),
                        "b2b_monthly_in_hand_inr": 885000,
                        "eor_monthly_in_hand_inr": 365000,
                        "submission_evidence_at": item.get("timestamp") if has_receipt else None,
                        "submission_evidence_source": proof_ref if has_receipt else None,
                        "notes": sanitize_no_emdashes(f"Direct Easy-Apply via {item.get('platform')} using meenakannan92@gmail.com ({status_str})"),
                    })
                    existing_ids.add(jid)
                    existing_urls.add(item.get("url"))
        except Exception:
            pass

    # Merge Discovered Global B2B & India Remote Roles
    global_jobs_path = Path(__file__).parent / "discovered_global_jobs.json"
    if global_jobs_path.exists():
        try:
            global_items = json.loads(global_jobs_path.read_text(encoding="utf-8"))
            for idx_g, gitem in enumerate(global_items, 1):
                jid = gitem.get("id") or f"global_b2b_{idx_g}"
                if jid not in existing_ids and gitem.get("url") not in existing_urls:
                    st = gitem.get("status", "SHORTLISTED")
                    evidence_at = gitem.get("submission_evidence_at")
                    evidence_source = gitem.get("submission_evidence_source")
                    has_receipt = bool(evidence_at and evidence_source) and st == "CONFIRMED_SUBMITTED"
                    submit_attempted = st in ("APPLIED", "SUBMIT_CLICKED", "SUBMITTED", "SUBMITTED_UNVERIFIED")
                    lifecycle_stage = (
                        "APPLIED"
                        if has_receipt
                        else "SUBMITTED_UNVERIFIED"
                        if submit_attempted or st == "CONFIRMED_SUBMITTED"
                        else "SHORTLISTED"
                    )
                    jobs.append({
                        "job_id": jid,
                        "title": sanitize_no_emdashes(gitem.get("title", "")),
                        "company": sanitize_no_emdashes(gitem.get("company", "")),
                        "location": sanitize_no_emdashes(gitem.get("location", "100% Remote (India / Global B2B)")),
                        "platform": sanitize_no_emdashes(gitem.get("platform", "Global B2B / ATS")),
                        "url": gitem.get("url", ""),
                        "match_score": int(gitem.get("match_score", 95)),
                        "lifecycle_stage": lifecycle_stage,
                        "work_location_status": gitem.get("work_location_status") or "NEEDS_REVIEW",
                        "work_location_evidence": gitem.get("work_location_evidence", ""),
                        "b2b_monthly_in_hand_inr": 910000,
                        "eor_monthly_in_hand_inr": 375000,
                        "submission_evidence_at": evidence_at if has_receipt else None,
                        "submission_evidence_source": evidence_source if has_receipt else None,
                        "notes": sanitize_no_emdashes(f"{gitem.get('compensation', '')} | {st}"),
                    })
                    existing_ids.add(jid)
                    existing_urls.add(gitem.get("url"))
        except Exception:
            pass

    vault_versions = memory.vault.list_versions()
    rules = memory.get_active_rules()

    cur = memory.local_conn.cursor()
    timeline_rows = cur.execute(
        "SELECT * FROM application_timeline_events ORDER BY event_id DESC LIMIT 25"
    ).fetchall()
    timeline = [dict(r) for r in timeline_rows]

    stage_counts = {
        "TOTAL_FETCHED": len(jobs),
        "SHORTLISTED": sum(
            1 for j in jobs
            if j["lifecycle_stage"] == "SHORTLISTED"
            and j.get("work_location_status") == "VERIFIED"
            and int(j.get("match_score") or 0) >= 75
        ),
        "SHORTLISTED_REVIEW": sum(
            1 for j in jobs
            if j["lifecycle_stage"] in ("SHORTLISTED", "APPROVED")
            and (
                j.get("work_location_status", "NEEDS_REVIEW") != "VERIFIED"
                or int(j.get("match_score") or 0) < 75
            )
        ),
        "APPROVED": sum(
            1 for j in jobs
            if j["lifecycle_stage"] == "APPROVED" and j.get("work_location_status") == "VERIFIED"
        ),
        "APPLIED": sum(1 for j in jobs if j["lifecycle_stage"] == "APPLIED"),
        "APPLIED_WITHOUT_RECEIPT": applied_without_receipt,
        "SUBMITTED_UNVERIFIED": sum(
            1 for j in jobs if j.get("lifecycle_stage") == "SUBMITTED_UNVERIFIED"
        ),
        "SUBMITTED_CONFIRMED": sum(
            1 for j in jobs if j.get("submission_evidence_at") and j.get("submission_evidence_source")
        ),
        "ACKNOWLEDGED": sum(
            1 for j in jobs if j.get("acknowledged_at") and j.get("acknowledgement_evidence_source")
        ),
        "INDIA_ELIGIBILITY_VERIFIED": sum(1 for j in jobs if j.get("work_location_status") == "VERIFIED"),
        "ELIGIBILITY_NEEDS_REVIEW": sum(
            1 for j in jobs
            if j.get("work_location_status", "NEEDS_REVIEW") == "NEEDS_REVIEW"
            and j["lifecycle_stage"] != "DEAD_ZONE"
        ),
        "ELIGIBILITY_INELIGIBLE": sum(1 for j in jobs if j.get("work_location_status") == "INELIGIBLE"),
        "INTERVIEW": sum(1 for j in jobs if j["lifecycle_stage"] == "INTERVIEW"),
        "DEAD_ZONE": sum(1 for j in jobs if j["lifecycle_stage"] == "DEAD_ZONE"),
    }

    human_feedback_count = cur.execute("SELECT COUNT(*) FROM human_feedback_events").fetchone()[0]
    active_jobs = [
        j for j in jobs
        if j["lifecycle_stage"] != "DEAD_ZONE" and j.get("work_location_status") == "VERIFIED"
    ]
    avg_b2b_inhand = (
        round(sum(j["b2b_monthly_in_hand_inr"] for j in active_jobs) / len(active_jobs))
        if active_jobs
        else None
    )
    avg_eor_inhand = (
        round(sum(j["eor_monthly_in_hand_inr"] for j in active_jobs) / len(active_jobs))
        if active_jobs
        else None
    )

    return {
        "candidate_name": memory.profile.get("candidate_name", "Meena Kannan"),
        "headline": sanitize_no_emdashes(memory.profile.get("headline", "")),
        "backend_mode": memory.backend_mode,
        "stage_counts": stage_counts,
        "analytics": {
            "verified_role_count": len(active_jobs),
            "avg_b2b_monthly_in_hand_inr": avg_b2b_inhand,
            "avg_eor_monthly_in_hand_inr": avg_eor_inhand,
            "monthly_b2b_advantage_inr": avg_b2b_inhand - avg_eor_inhand if active_jobs else None,
            "consolidated_rules_count": len(rules),
            "human_feedback_count": human_feedback_count,
        },
        "rules": rules,
        "jobs": jobs,
        "vault_versions": vault_versions,
        "timeline": timeline,
        "agent_runtime": AgentRunLedger().snapshot(),
        "adaptive_quality": load_ranker_quality_report(memory.local_conn),
    }


async def index_page(request: Request) -> HTMLResponse:
    html_content = UI_FILE.read_text(encoding="utf-8")
    return HTMLResponse(html_content)


async def api_get_state(request: Request) -> JSONResponse:
    payload = build_state_payload()
    return JSONResponse(payload)


async def api_get_runs(request: Request) -> JSONResponse:
    return JSONResponse(AgentRunLedger().snapshot())


async def api_get_system(request: Request) -> JSONResponse:
    observation = inspect_runtime()
    status_code = 503 if observation.status == ObservationStatus.ERROR else 200
    return JSONResponse(observation.to_dict(), status_code=status_code)


async def api_get_capabilities(request: Request) -> JSONResponse:
    observation = capability_observation()
    status_code = 503 if observation.status == ObservationStatus.ERROR else 200
    return JSONResponse(observation.to_dict(), status_code=status_code)


async def api_get_quality(request: Request) -> JSONResponse:
    database_uri = SETTINGS.oracle.local_fallback_db.resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(database_uri, uri=True, timeout=10)
    except sqlite3.Error:
        return JSONResponse({"error": "Local job database is unavailable"}, status_code=503)
    conn.row_factory = sqlite3.Row
    try:
        payload = load_ranker_quality_report(conn)
    finally:
        conn.close()
    return JSONResponse(payload)


async def api_get_run(request: Request) -> JSONResponse:
    run_id = str(request.path_params.get("run_id", ""))
    ledger = AgentRunLedger()
    run = next((item for item in ledger.recent_runs(limit=50) if item["run_id"] == run_id), None)
    if not run:
        return JSONResponse({"error": "Run not found"}, status_code=404)
    return JSONResponse({"run": run, "events": ledger.run_events(run_id)})


async def api_transition_stage(request: Request) -> JSONResponse:
    body = await request.json()
    job_id = str(body.get("job_id", ""))
    new_stage = str(body.get("new_stage", "APPROVED"))
    note = sanitize_no_emdashes(str(body.get("note", "")))[:1000]
    closure_reason = sanitize_no_emdashes(str(body.get("closure_reason", "")))
    evidence_source = sanitize_no_emdashes(str(body.get("evidence_source", "")))[:500]

    memory = OracleAIMemoryManager()
    try:
        res = memory.update_job_lifecycle_stage(
            job_id=job_id,
            new_stage=new_stage,
            note=note,
            closure_reason=closure_reason,
            evidence_source=evidence_source,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    return JSONResponse({"ok": True, "transition": res, "state": build_state_payload()})


async def api_verify_work_location(request: Request) -> JSONResponse:
    body = await request.json()
    job_id = str(body.get("job_id", "")).strip()
    evidence = sanitize_no_emdashes(str(body.get("evidence", ""))).strip()[:1500]
    if not job_id or len(evidence) < 20:
        return JSONResponse(
            {"error": "Paste at least 20 characters of exact remote location or work eligibility text from the official posting"},
            status_code=400,
        )
    if not global_remote_evidence("", evidence):
        return JSONResponse(
            {"error": "The evidence must explicitly say remote from India or worldwide remote contractor eligibility"},
            status_code=400,
        )

    memory = OracleAIMemoryManager()
    row = memory.local_conn.execute(
        "SELECT lifecycle_stage, work_location_status FROM agent_episodic_memories WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    if not row:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if row["work_location_status"] == "INELIGIBLE":
        return JSONResponse({"error": "This role is recorded as ineligible from India"}, status_code=409)
    if row["lifecycle_stage"] == "DEAD_ZONE":
        return JSONResponse({"error": "Restore the role for review before verifying its location"}, status_code=409)

    memory.local_conn.execute(
        "UPDATE agent_episodic_memories SET work_location_status = 'VERIFIED', work_location_evidence = ? WHERE job_id = ?",
        (f"Manual review of official posting: {evidence}", job_id),
    )
    memory.local_conn.commit()
    return JSONResponse({"ok": True, "state": build_state_payload()})


async def api_log_acknowledgement(request: Request) -> JSONResponse:
    body = await request.json()
    job_id = str(body.get("job_id", "")).strip()
    note = sanitize_no_emdashes(str(body.get("note", "")))[:500]
    evidence_source = sanitize_no_emdashes(str(body.get("evidence_source", "")))[:500]
    if not job_id or len(note.strip()) < 12 or len(evidence_source.strip()) < 4:
        return JSONResponse(
            {"error": "job_id, acknowledgement text, and an evidence reference are required"},
            status_code=400,
        )

    memory = OracleAIMemoryManager()
    row = memory.local_conn.execute(
        "SELECT lifecycle_stage, acknowledged_at, submission_evidence_at, submission_evidence_source "
        "FROM agent_episodic_memories WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    if not row:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if row["lifecycle_stage"] not in ("APPLIED", "INTERVIEW", "OFFER"):
        return JSONResponse({"error": "Record the application before its acknowledgement"}, status_code=409)
    if not row["submission_evidence_at"] or not row["submission_evidence_source"]:
        return JSONResponse({"error": "Record the application receipt and its evidence reference first"}, status_code=409)
    if row["acknowledged_at"]:
        return JSONResponse({"error": "An acknowledgement is already recorded for this application"}, status_code=409)

    acknowledged_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    memory.local_conn.execute(
        "UPDATE agent_episodic_memories SET acknowledged_at = ?, acknowledgement_evidence_source = ? WHERE job_id = ?",
        (acknowledged_at, evidence_source.strip(), job_id),
    )
    memory.local_conn.execute(
        """
        INSERT INTO application_timeline_events (job_id, from_stage, to_stage, note, event_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            job_id,
            row["lifecycle_stage"],
            row["lifecycle_stage"],
            sanitize_no_emdashes(f"ATS acknowledgement: {note.strip()} | Evidence reference: {evidence_source.strip()}"),
            acknowledged_at,
        ),
    )
    memory.local_conn.commit()
    return JSONResponse({"ok": True, "state": build_state_payload()})


async def api_tax_simulate(request: Request) -> JSONResponse:
    body = await request.json()
    amount = float(body.get("amount", 85000))
    currency = str(body.get("currency", "USD")).upper()
    fx = FX_TO_INR.get(currency, 83.5)
    gross_inr = amount * fx
    calc = calculate_b2b_vs_employee_takehome(gross_inr)
    return JSONResponse({"ok": True, "input_amount": amount, "currency": currency, "fx_rate": fx, "result": calc})


async def api_prepare_materials(request: Request) -> JSONResponse:
    import subprocess
    from config import BASE_DIR
    try:
        subprocess.run(
            ['uv', 'run', 'python', '-m', 'scheduler_24_7', '--prepare-approved-materials'],
            cwd=str(BASE_DIR),
            check=True,
        )
        return JSONResponse({
            'ok': True,
            'message': 'Approved application materials prepared locally. Application submission remains human-controlled.',
        })
    except subprocess.CalledProcessError as e:
        return JSONResponse({'error': str(e)}, status_code=500)


async def api_scan_now(request: Request) -> JSONResponse:
    try:
        await run_discovery_cycle(force_rescore=False)
    except RunAlreadyActive as exc:
        return JSONResponse(
            {
                "error": "A discovery cycle is already running.",
                "active_run_id": exc.run_id,
                "phase": exc.phase,
                "agent_runtime": AgentRunLedger().snapshot(),
            },
            status_code=409,
        )
    except RunRecoveryRequired as exc:
        return JSONResponse(
            {
                "error": "A previous discovery run is stale. Inspect its owning process before recording recovery.",
                "stale_run_id": exc.run_id,
                "agent_runtime": AgentRunLedger().snapshot(),
            },
            status_code=409,
        )
    return JSONResponse({"ok": True, "state": build_state_payload()})


async def api_download_pdf(request: Request):
    ver_id = request.path_params.get("version_id", "")
    memory = OracleAIMemoryManager()
    row = memory.local_conn.execute(
        "SELECT * FROM resume_vault_versions WHERE version_id = ?", (ver_id,)
    ).fetchone()
    if not row:
        return JSONResponse({"error": "Version not found"}, status_code=404)
    html_rel = row["internal_vault_path"]
    ats_pdf = row["ats_upload_filename"]
    html_path = BASE_DIR / html_rel
    pdf_path = html_path.parent / ats_pdf
    pdf_is_current = (
        pdf_path.exists()
        and html_path.exists()
        and pdf_path.stat().st_mtime_ns >= html_path.stat().st_mtime_ns
    )
    if pdf_is_current:
        return FileResponse(str(pdf_path), media_type="application/pdf", filename=ats_pdf)
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return JSONResponse({"error": "Resume source file not found"}, status_code=404)


async def api_get_tables(request: Request) -> JSONResponse:
    memory = OracleAIMemoryManager()
    cur = memory.local_conn.cursor()
    existing_tables = {
        row["name"]
        for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    curated_list = []
    for name, meta in CURATED_TABLES.items():
        if name in existing_tables:
            curated_list.append({
                "table_name": name,
                "display_name": meta["display_name"],
                "description": meta["description"],
                "columns": meta["columns"],
            })
    return JSONResponse({
        "tables": [item["table_name"] for item in curated_list],
        "catalog": curated_list,
    })


async def api_get_table_data(request: Request) -> JSONResponse:
    table_name = str(request.path_params.get("table_name", "")).strip()
    if table_name not in CURATED_TABLES:
        return JSONResponse(
            {"error": "Access denied: table is not permitted in curated operational view"},
            status_code=400,
        )

    meta = CURATED_TABLES[table_name]
    allowed_cols = meta["columns"]

    try:
        limit = min(max(int(request.query_params.get("limit", 50)), 1), 200)
    except (ValueError, TypeError):
        limit = 50

    search_query = sanitize_no_emdashes(str(request.query_params.get("search", "")).strip()[:100])
    status_filter = sanitize_no_emdashes(str(request.query_params.get("status", "")).strip()[:50])

    memory = OracleAIMemoryManager()
    cur = memory.local_conn.cursor()

    exists = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    if not exists:
        return JSONResponse({"error": "Table not found"}, status_code=404)

    pragma_cols = {row["name"] for row in cur.execute(f"PRAGMA table_info({table_name})").fetchall()}
    cols_to_query = [col for col in allowed_cols if col in pragma_cols]
    if not cols_to_query:
        return JSONResponse({"columns": [], "data": [], "count": 0, "total": 0, "limit": limit})

    where_clauses: list[str] = []
    params: list[Any] = []

    if status_filter:
        filter_col = resolve_curated_status_filter_column(table_name, status_filter, cols_to_query)
        if filter_col:
            where_clauses.append(f'"{filter_col}" = ?')
            canonical = status_filter.strip().upper()
            known_keywords = {
                "SHORTLISTED", "APPROVED", "APPLIED", "INTERVIEW", "OFFER", "DEAD_ZONE",
                "VERIFIED", "NEEDS_REVIEW", "INELIGIBLE",
                "SUCCESS", "RUNNING", "FAILED", "STALE", "IDLE",
            }
            params.append(canonical if canonical in known_keywords else status_filter.strip())

    if search_query:
        search_cols = [
            c for c in cols_to_query
            if c in ("title", "company", "job_id", "name", "workflow", "source_platform")
        ]
        if search_cols:
            search_clause = " OR ".join(f'"{c}" LIKE ?' for c in search_cols)
            where_clauses.append(f"({search_clause})")
            params.extend([f"%{search_query}%"] * len(search_cols))

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    order_by_sql = f"ORDER BY {meta.get('default_order_by', cols_to_query[0])}"

    cols_sql = ", ".join(f'"{c}"' for c in cols_to_query)
    query_sql = f"SELECT {cols_sql} FROM {table_name} {where_sql} {order_by_sql} LIMIT ?"
    query_params = list(params) + [limit]

    rows = cur.execute(query_sql, query_params).fetchall()

    count_sql = f"SELECT COUNT(*) FROM {table_name} {where_sql}"
    total = cur.execute(count_sql, params).fetchone()[0]

    data = []
    for r in rows:
        row_dict = {}
        for c in cols_to_query:
            row_dict[c] = sanitize_curated_value(r[c])
        data.append(row_dict)

    return JSONResponse({
        "table": table_name,
        "display_name": meta["display_name"],
        "columns": cols_to_query,
        "data": data,
        "count": len(data),
        "total": total,
        "limit": limit,
    })


FORBIDDEN_HOST_CHARS = set("/\\?#@;,%")


def parse_host_header(raw_host: str) -> str:
    """
    Safely extract the hostname from a Host header, failing closed for malformed
    syntax, invalid ports, or forbidden characters. Never trusts forwarded headers.
    """
    if not raw_host or not isinstance(raw_host, str):
        return ""

    # Reject whitespace and control characters anywhere in the host header
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in raw_host):
        return ""

    # Reject path, query, fragment, auth, and delimiter characters
    if any(c in FORBIDDEN_HOST_CHARS for c in raw_host):
        return ""

    # Bracketed IPv6: [::1] or [::1]:8080
    if raw_host.startswith("["):
        end_idx = raw_host.find("]")
        if end_idx == -1:
            return ""
        ip_inside = raw_host[1:end_idx]
        if not ip_inside:
            return ""
        try:
            normalized_ip = str(ipaddress.IPv6Address(ip_inside))
        except ValueError:
            return ""
        remainder = raw_host[end_idx + 1 :]
        if remainder:
            if not remainder.startswith(":"):
                return ""
            port_str = remainder[1:]
            if not port_str or len(port_str) > 5 or not re.fullmatch(r"^[0-9]+$", port_str):
                return ""
            try:
                port_val = int(port_str)
            except (ValueError, OverflowError):
                return ""
            if not (1 <= port_val <= 65535):
                return ""
        return normalized_ip

    # Reject stray brackets
    if "[" in raw_host or "]" in raw_host:
        return ""

    # IPv4 or hostname with optional port
    if ":" in raw_host:
        parts = raw_host.split(":")
        if len(parts) != 2:
            return ""
        host_part, port_str = parts
        if not port_str or len(port_str) > 5 or not re.fullmatch(r"^[0-9]+$", port_str):
            return ""
        try:
            port_val = int(port_str)
        except (ValueError, OverflowError):
            return ""
        if not (1 <= port_val <= 65535):
            return ""
    else:
        host_part = raw_host

    if not host_part or len(host_part) > 253:
        return ""

    labels = host_part.split(".")
    for label in labels:
        if not (1 <= len(label) <= 63):
            return ""
        if not re.fullmatch(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$", label):
            return ""

    return host_part.lower()


def get_allowed_hosts() -> Set[str]:
    """
    Allowed hosts: restricted to loopback by default (127.0.0.1, localhost, ::1),
    plus explicit comma-separated additions from APP_ALLOWED_HOSTS.
    Forwarded host headers are not used for authorization.
    """
    hosts: Set[str] = {"127.0.0.1", "localhost", "::1"}
    extra = os.environ.get("APP_ALLOWED_HOSTS", "").strip()
    if extra:
        for h in extra.split(","):
            cleaned = parse_host_header(h.strip())
            if cleaned:
                hosts.add(cleaned)
    return hosts


def get_allowed_origins() -> Set[str]:
    """
    Allowed exact origins: local defaults plus comma-separated APP_ALLOWED_ORIGINS additions.
    """
    origins: Set[str] = {
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    }
    extra = os.environ.get("APP_ALLOWED_ORIGINS", "").strip()
    if extra:
        for o in extra.split(","):
            cleaned = o.strip()
            if cleaned:
                origins.add(cleaned)
    return origins


def _get_raw_asgi_header(headers: List[tuple[bytes, bytes]], key_name: str) -> str:
    key_bytes = key_name.lower().encode("latin-1")
    matching = [v.decode("latin-1") for k, v in headers if k.lower() == key_bytes]
    if len(matching) == 1:
        return matching[0]
    return ""


def _get_asgi_header(headers: List[tuple[bytes, bytes]], key_name: str) -> str:
    key_bytes = key_name.lower().encode("latin-1")
    for k, v in headers:
        if k.lower() == key_bytes:
            return v.decode("latin-1").strip()
    return ""


def _parse_cookie_header(cookie_str: str) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


def _extract_asgi_cookies(headers: List[tuple[bytes, bytes]]) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    for k, v in headers:
        if k.lower() == b"cookie":
            cookies.update(_parse_cookie_header(v.decode("latin-1")))
    return cookies


class PrivateAccessSecurityMiddleware:
    """
    Pure ASGI middleware enforcing:
    1. Host header restriction to loopback (127.0.0.1, localhost, ::1) or APP_ALLOWED_HOSTS.
       Fails closed for malformed host syntax and invalid ports. Bracketed IPv6 values are
       validated with ipaddress and normalized. Forwarded headers (e.g. X-Forwarded-Host)
       are never trusted for authorization.
    2. Origin whitelist enforcement on all unsafe methods (methods outside GET, HEAD, OPTIONS).
       Request Origin is read as raw unstripped value and compared exactly against the configured allowlist.
    3. Double-submit CSRF token validation matching app_csrf cookie and X-CSRF-Token header
       using constant-time comparison (hmac.compare_digest).
    4. Cryptographically random app_csrf cookie issuance on GET / only after Host authorization passes,
       with Path=/ and SameSite=Strict (plus Secure if APP_CSRF_COOKIE_SECURE=true).
       Rejected Host responses never set app_csrf.
    5. Injection of hardened security headers on all responses.
    6. Note: Client-supplied Cloudflare Access headers (Cf-Access-Jwt-Assertion) are not
       validated here; cryptographic JWT verification occurs at the tunnel connector/origin.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        headers = scope.get("headers", [])

        # Send security response headers without setting any CSRF cookie
        async def send_security_headers_only(message: Dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                resp_headers = list(message.get("headers", []))
                resp_headers.append((b"x-content-type-options", b"nosniff"))
                resp_headers.append((b"x-frame-options", b"DENY"))
                resp_headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                resp_headers.append((b"permissions-policy", b"accelerometer=(), camera=(), geolocation=(), microphone=()"))
                message = {**message, "headers": resp_headers}
            await send(message)

        # 1. Host authorization (safe parsing, loopback default, no trust in forwarded headers)
        raw_host = _get_raw_asgi_header(headers, "host")
        host_name = parse_host_header(raw_host)
        allowed_hosts = get_allowed_hosts()
        if not host_name or host_name not in allowed_hosts:
            resp = JSONResponse(
                {"error": "Forbidden: untrusted Host header"},
                status_code=403,
            )
            # Rejected Host response must never set app_csrf cookie
            await resp(scope, receive, send_security_headers_only)
            return

        # 2. Mutating method protection: every unsafe HTTP method (outside GET, HEAD, OPTIONS)
        is_safe_method = method in ("GET", "HEAD", "OPTIONS")
        if not is_safe_method:
            origin = _get_raw_asgi_header(headers, "origin")
            allowed_origins = get_allowed_origins()
            # Compare request Origin exactly against configured allowlist (no stripping trailing slashes or padding)
            if not origin or origin not in allowed_origins:
                resp = JSONResponse(
                    {"error": "Forbidden: invalid or missing Origin header"},
                    status_code=403,
                )
                await resp(scope, receive, send_security_headers_only)
                return

            cookies = _extract_asgi_cookies(headers)
            cookie_csrf = cookies.get("app_csrf", "")
            header_csrf = _get_asgi_header(headers, "x-csrf-token")

            if (
                not cookie_csrf
                or not header_csrf
                or not hmac.compare_digest(cookie_csrf, header_csrf)
            ):
                resp = JSONResponse(
                    {"error": "Forbidden: invalid or missing CSRF token"},
                    status_code=403,
                )
                await resp(scope, receive, send_security_headers_only)
                return

        # 3. Issue CSRF cookie on GET / only after Host authorization passes
        csrf_cookie_val = ""
        if method == "GET" and path == "/":
            csrf_token = secrets.token_urlsafe(32)
            cookie_parts = [f"app_csrf={csrf_token}", "Path=/", "SameSite=Strict"]
            if os.environ.get("APP_CSRF_COOKIE_SECURE", "").strip().lower() == "true":
                cookie_parts.append("Secure")
            csrf_cookie_val = "; ".join(cookie_parts)

        async def send_with_security_headers(message: Dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                resp_headers = list(message.get("headers", []))
                resp_headers.append((b"x-content-type-options", b"nosniff"))
                resp_headers.append((b"x-frame-options", b"DENY"))
                resp_headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                resp_headers.append((b"permissions-policy", b"accelerometer=(), camera=(), geolocation=(), microphone=()"))
                if csrf_cookie_val:
                    resp_headers.append((b"set-cookie", csrf_cookie_val.encode("latin-1")))
                message = {**message, "headers": resp_headers}
            await send(message)

        # Cloudflare Access JWT validation must occur at the tunnel connector/origin.
        # Client-supplied headers are never trusted directly for authorization.
        await self.app(scope, receive, send_with_security_headers)


app = Starlette(
    debug=False,
    middleware=[Middleware(PrivateAccessSecurityMiddleware)],
    routes=[
        Route("/", index_page, methods=["GET"]),
        Route("/api/state", api_get_state, methods=["GET"]),
        Route("/api/runs", api_get_runs, methods=["GET"]),
        Route("/api/runs/{run_id}", api_get_run, methods=["GET"]),
        Route("/api/system", api_get_system, methods=["GET"]),
        Route("/api/capabilities", api_get_capabilities, methods=["GET"]),
        Route("/api/quality", api_get_quality, methods=["GET"]),
        Route("/api/transition", api_transition_stage, methods=["POST"]),
        Route("/api/eligibility/verify", api_verify_work_location, methods=["POST"]),
        Route("/api/acknowledge", api_log_acknowledgement, methods=["POST"]),
        Route("/api/tax-simulate", api_tax_simulate, methods=["POST"]),
        Route("/api/scan-now", api_scan_now, methods=["POST"]),
        Route("/api/prepare-materials", api_prepare_materials, methods=["POST"]),
        Route("/api/download-pdf/{version_id}", api_download_pdf, methods=["GET"]),
        Route("/api/tables", api_get_tables, methods=["GET"]),
        Route("/api/table_data/{table_name}", api_get_table_data, methods=["GET"]),
    ],
)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
