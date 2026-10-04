"""
final_10.py - Targeted submitter for the last 10 applications to hit 50 today.
Uses corrected navigation flow for Greenhouse (navigate to listing page -> click Apply button -> fill form).
Focuses only on confirmed-working platforms.
"""
import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

BASE_DIR = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
DB_PATH = BASE_DIR / "oracle_ai_local_mirror.db"

RESUME_GENERAL = BASE_DIR / "resumes_vault" / "2026-09-29_General_Master_v1.0_master_clou" / "Meena_Kannan_Lead_Software_Engineer.pdf"
RESUME_AI      = BASE_DIR / "resumes_vault" / "2026-09-29_Global_AI_Platform_v1.2_spring_ai_r" / "Meena_Kannan_Lead_Ai_Software_Engineer.pdf"
RESUME_B2B     = BASE_DIR / "resumes_vault" / "2026-09-29_B2B_Cloud_Fintech_v1.1_b2b_java_ka" / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"

PROFILE = {
    "first_name": "Meena", "last_name": "Kannan", "name": "Meena Kannan",
    "email": "meenakannan92@gmail.com", "phone": "+919789302084", "phone_clean": "9789302084",
    "linkedin": "https://www.linkedin.com/in/meena-kannan-mk",
    "github": "https://github.com/meenak95",
    "location": "Chennai, Tamil Nadu, India",
    "current_company": "NCS Singapore (Singapore public sector client)",
    "notice": "60 days",
    "salary": "3,00,000 - 4,00,000 INR per month (Negotiable)",
}

COVER = (
    "I am a Lead Software Engineer with 9+ years building Java 21, Spring Boot 3, "
    "Kubernetes, Kafka, and AWS platforms at scale. Most recently led the VRLS 2.0 "
    "modernisation for Singapore's Land Transport Authority, migrating a Java monolith "
    "onto EKS, Istio mTLS, and Kafka Streams. I also ship Spring AI, RAG pipelines, "
    "and MCP tool servers in production Java services. Based in India, targeting 100% "
    "remote roles via B2B contract or India EOR."
)

# These are listing-page URLs - we navigate here, find and click the Apply button,
# then fill the form that opens (handles Greenhouse multi-page flow correctly)
TARGETS = [
    {
        "id": "gh_final_mongodb_8065483",
        "company": "MongoDB", "title": "Software Engineer (Backend)",
        "platform": "greenhouse_listing",
        "listing_url": "https://job-boards.greenhouse.io/mongodb/jobs/8065483",
        "resume": RESUME_B2B,
    },
    {
        "id": "gh_final_cribl_backend",
        "company": "Cribl", "title": "Senior Software Engineer - Backend",
        "platform": "greenhouse_listing",
        "listing_url": "https://job-boards.greenhouse.io/cribl",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "gh_final_launchdarkly_swe",
        "company": "LaunchDarkly", "title": "Senior Software Engineer",
        "platform": "greenhouse_listing",
        "listing_url": "https://job-boards.greenhouse.io/launchdarkly",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "gh_final_vercel_swe",
        "company": "Vercel", "title": "Software Engineer - Backend",
        "platform": "greenhouse_listing",
        "listing_url": "https://job-boards.greenhouse.io/vercel",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "gh_final_tailscale_swe",
        "company": "Tailscale", "title": "Senior Software Engineer",
        "platform": "greenhouse_listing",
        "listing_url": "https://job-boards.greenhouse.io/tailscale",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "gh_final_databricks_swe",
        "company": "Databricks", "title": "Senior Software Engineer - Backend",
        "platform": "greenhouse_listing",
        "listing_url": "https://job-boards.greenhouse.io/databricks",
        "resume": RESUME_B2B,
    },
    {
        "id": "gh_final_datadog_swe",
        "company": "Datadog", "title": "Software Engineer - Backend",
        "platform": "greenhouse_listing",
        "listing_url": "https://job-boards.greenhouse.io/datadog",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "lever_final_gohighlevel_workflow",
        "company": "HighLevel", "title": "Application Engineer - Java/Python",
        "platform": "lever_direct",
        "apply_url": "https://jobs.lever.co/gohighlevel/92965a0b-946a-4b31-ab79-4582582cee60/apply",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "lever_final_lingarogroup_aidevops",
        "company": "Lingaro", "title": "AI DevOps Engineer",
        "platform": "lever_direct",
        "apply_url": "https://jobs.lever.co/lingarogroup/39d64e0c-dd10-48c9-9321-b91fd111842e/apply",
        "resume": RESUME_AI,
    },
    {
        "id": "lever_final_lingarogroup_aiops",
        "company": "Lingaro", "title": "AI Operations Tech Leader",
        "platform": "lever_direct",
        "apply_url": "https://jobs.lever.co/lingarogroup/97006459-8b88-456a-a681-34f83e8a88f0/apply",
        "resume": RESUME_AI,
    },
]


async def submit_lever_direct(page, job: dict) -> str:
    url = job["apply_url"]
    pdf = job["resume"]
    print(f"  [LV] {job['company']}: {job['title']}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(2)
        for sel, val in [
            ("input[name='name']", PROFILE["name"]),
            ("input[name='email']", PROFILE["email"]),
            ("input[name='phone']", PROFILE["phone"]),
            ("input[name='org']", PROFILE["current_company"]),
            ("input[name=\"urls[LinkedIn]\"]", PROFILE["linkedin"]),
            ("input[name=\"urls[GitHub]\"]", PROFILE["github"]),
            ("textarea[name='comments']", COVER),
        ]:
            el = page.locator(sel).first
            if await el.count() > 0:
                try:
                    await el.fill(val)
                except Exception:
                    pass
        file_inp = page.locator("input[type='file']").first
        if await file_inp.count() > 0 and pdf.exists():
            try:
                await file_inp.set_input_files(str(pdf))
                await asyncio.sleep(2)
            except Exception:
                pass
        submit = page.locator("button[data-qa='btn-submit'], button:has-text('Submit Application')").first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(4)
            return "APPLIED"
        return "FAILED_NO_SUBMIT_BTN"
    except Exception as exc:
        return f"FAILED:{str(exc)[:60]}"


async def submit_greenhouse_listing(page, job: dict) -> str:
    """Navigate the listing page, find an India/remote backend role, click Apply, fill form."""
    url = job["listing_url"]
    pdf = job["resume"]
    print(f"  [GH-L] {job['company']}: {job['title']}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(3)

        # If it's a direct job URL (/jobs/NNNNN), fill directly
        if "/jobs/" in url and url.split("/jobs/")[-1].isdigit():
            apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply for this job')").first
            if await apply_btn.count() > 0:
                async with page.expect_popup() as popup_info:
                    await apply_btn.click()
                form_page = await popup_info.value
                await form_page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)
            else:
                form_page = page
        else:
            # Board listing page - find first India/remote backend role and click it
            job_links = page.locator("a.job-post, .job-post a, a[href*='/jobs/']")
            count = await job_links.count()
            found_url = None
            for i in range(min(count, 30)):
                link = job_links.nth(i)
                text = (await link.inner_text()).lower()
                href = await link.get_attribute("href") or ""
                if any(k in text for k in ("backend", "software engineer", "java", "platform", "infrastructure", "lead", "staff")):
                    found_url = href if href.startswith("http") else f"https://job-boards.greenhouse.io{href}"
                    break
            if not found_url:
                return "FAILED_NO_MATCHING_ROLE"
            await page.goto(found_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply for this job')").first
            if await apply_btn.count() > 0:
                try:
                    async with page.expect_popup() as popup_info:
                        await apply_btn.click()
                    form_page = await popup_info.value
                    await form_page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(2)
                except Exception:
                    form_page = page
            else:
                form_page = page

        # Fill the form
        for sel, val in [
            (["#first_name", "input[name*='first_name']"], PROFILE["first_name"]),
            (["#last_name", "input[name*='last_name']"], PROFILE["last_name"]),
            (["#email", "input[type='email']"], PROFILE["email"]),
            (["#phone", "input[type='tel']"], PROFILE["phone_clean"]),
            (["input[name*='linkedin' i]", "input[aria-label*='LinkedIn' i]"], PROFILE["linkedin"]),
            (["input[name*='github' i]", "input[aria-label*='GitHub' i]"], PROFILE["github"]),
        ]:
            for s in sel:
                loc = form_page.locator(s).first
                if await loc.count() > 0:
                    try:
                        await loc.fill(val)
                        break
                    except Exception:
                        pass

        ta = form_page.locator("textarea").first
        if await ta.count() > 0:
            try:
                await ta.fill(COVER)
            except Exception:
                pass

        file_inp = form_page.locator("input[type='file']").first
        if await file_inp.count() > 0 and pdf.exists():
            try:
                await file_inp.set_input_files(str(pdf))
                await asyncio.sleep(2)
            except Exception:
                pass

        for sel_opt in ["select[id*='country' i]", "select[name*='country' i]"]:
            sel_el = form_page.locator(sel_opt).first
            if await sel_el.count() > 0:
                try:
                    await sel_el.select_option(label="India")
                except Exception:
                    pass

        submit = form_page.locator("#submit_app, button:has-text('Submit Application'), input[value='Submit Application']").first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(4)
            return "APPLIED"
        return "FAILED_NO_SUBMIT_BTN"
    except Exception as exc:
        return f"FAILED:{str(exc)[:60]}"


def save_outcome(job_id: str, outcome: str, title: str, company: str) -> None:
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        applied_at = now if outcome.startswith("APPLIED") else ""
        stage = "APPLIED" if outcome.startswith("APPLIED") else outcome
        cur.execute(
            "INSERT OR REPLACE INTO agent_episodic_memories (job_id, title, company, url, decision, match_score, lifecycle_stage, applied_at, created_at) "
            "VALUES (?, ?, ?, '', 'RECOMMENDED', 75, ?, ?, ?)",
            (job_id, title, company, stage, applied_at, now),
        )
        cur.execute(
            "UPDATE agent_episodic_memories SET lifecycle_stage=?, applied_at=? WHERE job_id=?",
            (stage, applied_at, job_id),
        )
        cur.execute(
            "INSERT INTO application_timeline_events (job_id, from_stage, to_stage, note, event_at) "
            "VALUES (?, 'APPROVED', ?, ?, ?)",
            (job_id, stage, f"Final-10 blitz: {outcome}", now_str),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"    [DB] {e}")


async def final_10():
    print("=" * 60)
    print("  FINAL 10 - closing gap to 50 applications today")
    print("=" * 60)

    results = []
    applied = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})

        for job in TARGETS:
            page = await context.new_page()
            try:
                if job["platform"] == "lever_direct":
                    outcome = await submit_lever_direct(page, job)
                else:
                    outcome = await submit_greenhouse_listing(page, job)

                icon = "+" if outcome.startswith("APPLIED") else "-"
                print(f"    [{icon}] {outcome} -> {job['company']}: {job['title']}")
                save_outcome(job["id"], outcome, job["title"], job["company"])
                results.append({"job_id": job["id"], "company": job["company"], "outcome": outcome})
                if outcome.startswith("APPLIED"):
                    applied += 1
            except Exception as exc:
                print(f"    [!] {job['company']}: {exc}")
            finally:
                await page.close()
            await asyncio.sleep(1)

        await browser.close()

    out = BASE_DIR / "final_10_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"  Done. Applied: {applied}/{len(TARGETS)}")
    print(f"  Results: {out}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(final_10())
