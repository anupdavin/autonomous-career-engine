import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from config import BASE_DIR
from guardrails import assert_no_emdashes, sanitize_no_emdashes
from oracle_memory import OracleAIMemoryManager


EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_edge_binary() -> str:
    for p in EDGE_PATHS:
        if Path(p).exists():
            return p
    return ""


def render_html_to_real_pdf(html_path: Path, pdf_path: Path) -> bool:
    """
    Uses Windows built-in Microsoft Edge headless engine to convert the tailored HTML
    resume directly into a real, clean ATS-ready PDF file (`Meena_Kannan_<Role>.pdf`)
    with zero headers/footers and zero manual printing required.
    """
    edge_bin = find_edge_binary()
    if not edge_bin:
        return False
    try:
        cmd = [
            edge_bin,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={str(pdf_path)}",
            str(html_path.resolve()),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        return pdf_path.exists() and pdf_path.stat().st_size > 1000
    except Exception:
        return False


def run_autonomous_autopilot(min_auto_score: int = 90) -> List[Dict[str, Any]]:
    """
    Autonomous Job Application Autopilot for Meena Kannan:
      1. Scans all SHORTLISTED / APPROVED jobs with Match Score >= min_auto_score (90/100).
      2. Auto-approves them and generates role-specific tailored resume snapshots (`v2.x`).
      3. Automatically compiles real `.pdf` files (`Meena_Kannan_<Clean_Role>.pdf`) via Edge Headless.
      4. Generates ready-to-send `cover_note.txt`, `recruiter_dm.txt`, `b2b_proposal.txt`, and `auto_fill_payload.json`.
      5. Advances the job status so Meena has zero manual prep work.
    """
    memory = OracleAIMemoryManager()
    jobs = memory.get_all_crm_jobs()
    processed: List[Dict[str, Any]] = []

    for job in jobs:
        if job["match_score"] < min_auto_score or job["lifecycle_stage"] == "DEAD_ZONE":
            continue

        job_id = job["job_id"]
        # 1. Auto-Approve & Generate Tailored Resume Version in Vault if still SHORTLISTED
        if job["lifecycle_stage"] == "SHORTLISTED":
            memory.update_job_lifecycle_stage(
                job_id=job_id,
                new_stage="APPROVED",
                note=f"Autopilot auto-approved ({job['match_score']}/100 match) & built PDF application kit",
            )

        # Reload updated job & its assigned vault version
        cur = memory.local_conn.cursor()
        updated_job = dict(
            cur.execute("SELECT * FROM agent_episodic_memories WHERE job_id = ?", (job_id,)).fetchone()
        )
        ver_id = updated_job["resume_version_id"]
        ver_row = cur.execute(
            "SELECT * FROM resume_vault_versions WHERE version_id = ?", (ver_id,)
        ).fetchone()
        if not ver_row:
            continue

        rel_html = ver_row["internal_vault_path"]
        html_file = BASE_DIR / rel_html
        folder = html_file.parent
        ats_pdf_name = ver_row["ats_upload_filename"]
        pdf_file = folder / ats_pdf_name

        # 2. Render real PDF file on disk
        pdf_ok = render_html_to_real_pdf(html_file, pdf_file)

        # 3. Generate Recruiter LinkedIn DM, Cover Note, and Auto-Fill Form Payload (0 Em-Dashes)
        clean_title = sanitize_no_emdashes(updated_job["title"].split("[")[0].split("(")[0].strip())
        clean_comp = sanitize_no_emdashes(updated_job["company"].split("(")[0].strip())
        pitch_text = sanitize_no_emdashes(updated_job["tailored_pitch"])

        recruiter_dm = sanitize_no_emdashes(
            f"Hi {clean_comp} Recruiting Team, I just applied for the {clean_title} role. "
            f"I bring 9+ years of Java 21, Spring Boot 3, AWS/Kubernetes, Kafka, and Spring AI/MCP experience "
            f"(currently Lead Engineer on VRLS 2.0) and am available immediately from India for 100% remote B2B or full-time work. "
            f"Shared my resume ({ats_pdf_name}) and would love to connect!"
        )
        assert_no_emdashes(recruiter_dm, "recruiter_dm")

        autofill_payload = {
            "candidate": {
                "first_name": "Meena",
                "last_name": "Kannan",
                "full_name": "Meena Kannan",
                "email": "meenakannan92@gmail.com",
                "phone": "+91 97893 02084",
                "location": "Chennai, India (100% Remote Worldwide / Global B2B or India EOR)",
                "linkedin_url": "https://www.linkedin.com/in/meena-kannan-mk",
                "github_url": "https://github.com/meenak95",
                "years_of_experience": 9,
                "notice_period": "Immediate / 15 Days",
                "engagement_models": ["Global B2B Contractor (USD/EUR/GBP via Deel/Invoicing)", "Full-Time Remote India (EOR)"],
            },
            "job_target": {
                "job_id": job_id,
                "title": clean_title,
                "company": clean_comp,
                "portal_url": updated_job["url"],
                "estimated_b2b_monthly_in_hand_inr": updated_job["b2b_monthly_in_hand_inr"],
                "estimated_eor_monthly_in_hand_inr": updated_job["eor_monthly_in_hand_inr"],
            },
            "files_prepared": {
                "employer_upload_pdf": str(pdf_file) if pdf_ok else str(html_file),
                "ats_safe_filename": ats_pdf_name,
                "cover_note_file": str(folder / "cover_note.txt"),
                "recruiter_dm_file": str(folder / "recruiter_linkedin_dm.txt"),
            },
        }

        (folder / "cover_note.txt").write_text(pitch_text, encoding="utf-8")
        (folder / "recruiter_linkedin_dm.txt").write_text(recruiter_dm, encoding="utf-8")
        (folder / "autofill_application_packet.json").write_text(
            json.dumps(autofill_payload, indent=2), encoding="utf-8"
        )

        processed.append(
            {
                "job_id": job_id,
                "title": clean_title,
                "company": clean_comp,
                "pdf_generated": pdf_ok,
                "pdf_path": str(pdf_file.relative_to(BASE_DIR)).replace("\\", "/") if pdf_ok else rel_html,
                "ats_filename": ats_pdf_name,
                "stage": updated_job["lifecycle_stage"],
            }
        )

    return processed


if __name__ == "__main__":
    results = run_autonomous_autopilot(min_auto_score=90)
    print(f"[Autopilot Complete] Auto-prepared {len(results)} complete PDF application kits:")
    for r in results:
        print(f"  * {r['company']} - {r['title']} | PDF={r['pdf_generated']} -> {r['pdf_path']}")
