"""Runner script for Semantic ATS Application Automation."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from playwright.async_api import async_playwright

from tools.apply_engine.semantic_driver import SemanticATSDriver

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_application")

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
VAULT_DIR = WORKSPACE_ROOT / "resumes_vault"


def resolve_best_resume(job_url: str, job_title: str = "") -> Path:
    """Select the most tailored verified PDF resume based on company and title."""
    target_str = (job_url + " " + job_title).lower()

    if "juniper" in target_str:
        p = VAULT_DIR / "2026-09-27_Juniper_Square_v2.30_ashby_juni" / "Meena_Kannan_Senior_Technical_Lead.pdf"
        if p.exists():
            return p
    if "oscilar" in target_str:
        p = VAULT_DIR / "2026-09-27_Oscilar_v2.29_ashby_osci" / "Meena_Kannan_Sr_Staff_Backend_Engineer.pdf"
        if p.exists():
            return p
    if "micro1" in target_str:
        p = VAULT_DIR / "2026-09-27_micro1_v2.28_b2b_micro1" / "Meena_Kannan_Senior_Lead_Backend_Java.pdf"
        if p.exists():
            return p
    if "mongodb" in target_str:
        p = VAULT_DIR / "2026-09-27_MongoDB_v2.21_gh_rem_mon" / "Meena_Kannan_Advisory_Partner_Solutions_Architect.pdf"
        if p.exists():
            return p
    if "neuraflash" in target_str:
        p = VAULT_DIR / "2026-09-27_NeuraFlash_Accenture_v2.42_gh_rem_neu" / "Meena_Kannan_Ai_Strategy_Transformation_Architect.pdf"
        if p.exists():
            return p

    # Role profile matches
    if any(k in target_str for k in ["ai", "mcp", "rag", "claude", "agent", "llm", "learning"]):
        p = VAULT_DIR / "2026-09-29_Global_AI_Platform_v1.2_spring_ai_r" / "Meena_Kannan_Lead_Ai_Software_Engineer.pdf"
        if p.exists():
            return p
    if any(k in target_str for k in ["b2b", "consult", "architect", "kafka", "fintech", "payments", "cloud"]):
        p = VAULT_DIR / "2026-09-29_B2B_Cloud_Fintech_v1.1_b2b_java_ka" / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"
        if p.exists():
            return p

    # Fallback to general master
    default_p = VAULT_DIR / "2026-09-29_General_Master_v1.0_master_clou" / "Meena_Kannan_Lead_Software_Engineer.pdf"
    if default_p.exists():
        return default_p

    # Any PDF in vault
    pdfs = list(VAULT_DIR.rglob("*.pdf"))
    if pdfs:
        return pdfs[0]

    raise FileNotFoundError("No resume PDF found in resumes_vault.")


async def execute_application(
    url: str,
    resume_path: Optional[Path] = None,
    cover_text: Optional[str] = None,
    job_id: str = "generic_job",
    auto_submit: bool = False,
    headless: bool = True
) -> dict:
    if resume_path is None or not resume_path.exists():
        resume_path = resolve_best_resume(url)

    logger.info(f"Target URL: {url}")
    logger.info(f"Resume: {resume_path.name}")
    logger.info(f"Mode: {'AUTO_SUBMIT' if auto_submit else 'HOLD_FOR_REVIEW (DRY-RUN)'}")

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(
                channel="chrome",
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
        except Exception:
            browser = await pw.chromium.launch(
                channel="msedge",
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            logger.info("Navigating to application page...")
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3.0)

            # If the page has an initial "Apply" or "Apply for this job" button, click it
            apply_opener = page.locator("a:has-text('Apply for this job'), button:has-text('Apply for this job'), a:has-text('Apply Now'), button:has-text('Apply Now')").first
            if await apply_opener.count() > 0:
                try:
                    await apply_opener.click(timeout=5000)
                    await asyncio.sleep(2.0)
                except Exception:
                    pass

            driver = SemanticATSDriver(page)
            traverse_result = await driver.traverse_portal(
                resume_path=resume_path,
                cover_text=cover_text,
                job_id=job_id,
                auto_submit=auto_submit
            )
            logger.info(f"Traverse result: status={traverse_result['status']}, pages={traverse_result['pages_processed']}, filled={traverse_result['filled_fields']}")

            result = {
                "job_id": job_id,
                "url": url,
                "resume_used": resume_path.name,
                "status": traverse_result["status"],
                "pages_processed": traverse_result.get("pages_processed", 1),
                "filled_fields": traverse_result.get("filled_fields", 0),
                "skipped_fields": traverse_result.get("skipped_fields", 0),
                "screenshot": traverse_result.get("screenshot"),
                "submission": traverse_result.get("submission"),
                "log": traverse_result.get("log", [])
            }
            return result
        finally:
            await browser.close()


def main():
    parser = argparse.ArgumentParser(description="Run semantic ATS job application.")
    parser.add_argument("url", help="Job application URL")
    parser.add_argument("--resume", help="Optional path to custom resume PDF")
    parser.add_argument("--job-id", default="manual_job", help="Identifier for DB tracking")
    parser.add_argument("--auto-submit", action="store_true", help="Submit under explicit human instruction")
    parser.add_argument("--headed", action="store_true", help="Launch visible browser")
    args = parser.parse_args()

    resume_p = Path(args.resume) if args.resume else None
    result = asyncio.run(
        execute_application(
            url=args.url,
            resume_path=resume_p,
            job_id=args.job_id,
            auto_submit=args.auto_submit,
            headless=not args.headed
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
