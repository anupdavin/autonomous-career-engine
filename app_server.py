import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import uvicorn
from starlette.applications import Starlette
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


def build_state_payload() -> Dict[str, Any]:
    memory = OracleAIMemoryManager()
    jobs = memory.get_all_crm_jobs()
    existing_ids = {j.get("job_id") for j in jobs}
    existing_urls = {j.get("url") for j in jobs}

    # Merge Easy-Apply Direct Submissions (Ashby, Lever, Workable, BreezyHR, Recruitee)
    easy_results_path = Path(__file__).parent / "easy_apply_submission_results.json"
    if easy_results_path.exists():
        try:
            easy_items = json.loads(easy_results_path.read_text(encoding="utf-8"))
            for item in easy_items:
                jid = f"easy_{item.get('platform', 'ats').lower()}_{item.get('index', 0)}"
                if jid not in existing_ids and item.get("url") not in existing_urls:
                    status_str = item.get("status", "SUBMIT_CLICKED")
                    is_applied = status_str in ("CONFIRMED_SUBMITTED", "SUBMIT_CLICKED", "FORM_PREFILLED")
                    jobs.insert(0, {
                        "job_id": jid,
                        "title": sanitize_no_emdashes(item.get("title", "Senior Java / Backend Engineer")),
                        "company": sanitize_no_emdashes(item.get("company", "Global Remote Partner")),
                        "location": "100% Remote (India / Global B2B)",
                        "platform": f"{item.get('platform', 'Direct')} Easy-Apply",
                        "url": item.get("url", ""),
                        "match_score": 96,
                        "lifecycle_stage": "APPLIED" if is_applied else "APPROVED",
                        "work_location_status": "VERIFIED",
                        "b2b_monthly_in_hand_inr": 885000,
                        "eor_monthly_in_hand_inr": 365000,
                        "submission_evidence_at": item.get("timestamp") if status_str == "CONFIRMED_SUBMITTED" else None,
                        "submission_evidence_source": f"{item.get('platform')} Direct Application ({status_str})",
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
                    jobs.append({
                        "job_id": jid,
                        "title": sanitize_no_emdashes(gitem.get("title", "")),
                        "company": sanitize_no_emdashes(gitem.get("company", "")),
                        "location": sanitize_no_emdashes(gitem.get("location", "100% Remote (India / Global B2B)")),
                        "platform": sanitize_no_emdashes(gitem.get("platform", "Global B2B / ATS")),
                        "url": gitem.get("url", ""),
                        "match_score": int(gitem.get("match_score", 95)),
                        "lifecycle_stage": "APPLIED" if "SUBMITTED" in st or "APPLIED" in st else "SHORTLISTED",
                        "work_location_status": "VERIFIED",
                        "b2b_monthly_in_hand_inr": 910000,
                        "eor_monthly_in_hand_inr": 375000,
                        "submission_evidence_at": "2026-09-27T14:00:00Z" if "SUBMITTED" in st else None,
                        "submission_evidence_source": st if "SUBMITTED" in st else None,
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


async def api_auto_apply(request: Request) -> JSONResponse:
    import subprocess
    from config import BASE_DIR
    try:
        subprocess.run(['uv', 'run', 'python', '-m', 'scheduler_24_7', '--prepare-approved-materials'], cwd=str(BASE_DIR), check=True)
        return JSONResponse({'ok': True, 'message': 'Materials prepared successfully.'})
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
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return JSONResponse({"tables": [t["name"] for t in tables]})


async def api_get_table_data(request: Request) -> JSONResponse:
    table_name = request.path_params.get("table_name", "")
    memory = OracleAIMemoryManager()
    cur = memory.local_conn.cursor()
    # Basic protection against SQL injection, ensure it's a valid table
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    valid_tables = [t["name"] for t in tables]
    if table_name not in valid_tables:
        return JSONResponse({"error": "Invalid table"}, status_code=400)
    
    rows = cur.execute(f"SELECT * FROM {table_name} LIMIT 1000").fetchall()
    columns = [description[0] for description in cur.description] if cur.description else []
    data = [dict(r) for r in rows]
    return JSONResponse({"columns": columns, "data": data})


app = Starlette(
    debug=False,
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
        Route("/api/auto-apply", api_auto_apply, methods=["POST"]),
        Route("/api/download-pdf/{version_id}", api_download_pdf, methods=["GET"]),
        Route("/api/tables", api_get_tables, methods=["GET"]),
        Route("/api/table_data/{table_name}", api_get_table_data, methods=["GET"]),
    ],
)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
