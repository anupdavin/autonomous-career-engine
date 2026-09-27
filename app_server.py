from pathlib import Path
from typing import Any, Dict

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Route

from auto_applicator import run_autonomous_autopilot
from config import BASE_DIR, SETTINGS
from guardrails import assert_no_emdashes, sanitize_no_emdashes
from oracle_memory import OracleAIMemoryManager
from scheduler_24_7 import run_discovery_cycle
from tax_salary_engine import FX_TO_INR, calculate_b2b_vs_employee_takehome

UI_FILE = Path(__file__).resolve().parent / "dashboard_ui.html"


def build_state_payload() -> Dict[str, Any]:
    memory = OracleAIMemoryManager()
    jobs = memory.get_all_crm_jobs()
    vault_versions = memory.vault.list_versions()
    rules = memory.get_active_rules()

    cur = memory.local_conn.cursor()
    timeline_rows = cur.execute(
        "SELECT * FROM application_timeline_events ORDER BY event_id DESC LIMIT 25"
    ).fetchall()
    timeline = [dict(r) for r in timeline_rows]
    skill_count = cur.execute("SELECT COUNT(*) FROM induced_skills").fetchone()[0]

    stage_counts = {
        "TOTAL_FETCHED": len(jobs),
        "SHORTLISTED": sum(1 for j in jobs if j["lifecycle_stage"] == "SHORTLISTED"),
        "APPROVED": sum(1 for j in jobs if j["lifecycle_stage"] == "APPROVED"),
        "APPLIED": sum(1 for j in jobs if j["lifecycle_stage"] == "APPLIED"),
        "INTERVIEW": sum(1 for j in jobs if j["lifecycle_stage"] == "INTERVIEW"),
        "DEAD_ZONE": sum(1 for j in jobs if j["lifecycle_stage"] == "DEAD_ZONE"),
    }

    active_jobs = [j for j in jobs if j["lifecycle_stage"] != "DEAD_ZONE"]
    avg_b2b_inhand = (
        round(sum(j["b2b_monthly_in_hand_inr"] for j in active_jobs) / len(active_jobs))
        if active_jobs
        else 520000
    )
    avg_eor_inhand = (
        round(sum(j["eor_monthly_in_hand_inr"] for j in active_jobs) / len(active_jobs))
        if active_jobs
        else 415000
    )

    return {
        "candidate_name": memory.profile.get("candidate_name", "Meena Kannan"),
        "headline": sanitize_no_emdashes(memory.profile.get("headline", "")),
        "backend_mode": memory.backend_mode,
        "stage_counts": stage_counts,
        "analytics": {
            "avg_b2b_monthly_in_hand_inr": avg_b2b_inhand,
            "avg_eor_monthly_in_hand_inr": avg_eor_inhand,
            "monthly_b2b_advantage_inr": avg_b2b_inhand - avg_eor_inhand,
            "induced_skills_count": skill_count,
            "consolidated_rules_count": len(rules),
        },
        "rules": rules,
        "jobs": jobs,
        "vault_versions": vault_versions,
        "timeline": timeline,
    }


async def index_page(request: Request) -> HTMLResponse:
    html_content = UI_FILE.read_text(encoding="utf-8")
    return HTMLResponse(html_content)


async def api_get_state(request: Request) -> JSONResponse:
    payload = build_state_payload()
    return JSONResponse(payload)


async def api_transition_stage(request: Request) -> JSONResponse:
    body = await request.json()
    job_id = str(body.get("job_id", ""))
    new_stage = str(body.get("new_stage", "APPROVED"))
    note = sanitize_no_emdashes(str(body.get("note", "")))
    closure_reason = sanitize_no_emdashes(str(body.get("closure_reason", "")))

    memory = OracleAIMemoryManager()
    res = memory.update_job_lifecycle_stage(
        job_id=job_id,
        new_stage=new_stage,
        note=note,
        closure_reason=closure_reason,
    )
    return JSONResponse({"ok": True, "transition": res, "state": build_state_payload()})


async def api_tax_simulate(request: Request) -> JSONResponse:
    body = await request.json()
    amount = float(body.get("amount", 85000))
    currency = str(body.get("currency", "USD")).upper()
    fx = FX_TO_INR.get(currency, 83.5)
    gross_inr = amount * fx
    calc = calculate_b2b_vs_employee_takehome(gross_inr)
    return JSONResponse({"ok": True, "input_amount": amount, "currency": currency, "fx_rate": fx, "result": calc})


async def api_scan_now(request: Request) -> JSONResponse:
    await run_discovery_cycle(force_rescore=False)
    run_autonomous_autopilot(min_auto_score=90)
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
    pdf_path = (BASE_DIR / html_rel).parent / ats_pdf
    if pdf_path.exists():
        return FileResponse(str(pdf_path), media_type="application/pdf", filename=ats_pdf)
    return FileResponse(str(BASE_DIR / html_rel), media_type="text/html", filename=ats_pdf.replace(".pdf", ".html"))


app = Starlette(
    debug=False,
    routes=[
        Route("/", index_page, methods=["GET"]),
        Route("/api/state", api_get_state, methods=["GET"]),
        Route("/api/transition", api_transition_stage, methods=["POST"]),
        Route("/api/tax-simulate", api_tax_simulate, methods=["POST"]),
        Route("/api/scan-now", api_scan_now, methods=["POST"]),
        Route("/api/download-pdf/{version_id}", api_download_pdf, methods=["GET"]),
    ],
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
