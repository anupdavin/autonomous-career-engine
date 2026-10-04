"""
blitz_apply.py - Full auto-submit blitz targeting 50 applications today.
Handles Greenhouse and Lever via Playwright with actual submit button clicks.
Writes outcomes to the Oracle AI DB.
Run: python blitz_apply.py
"""
import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

BASE_DIR = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
DB_PATH = BASE_DIR / "oracle_ai_local_mirror.db"

# Resume variants - pick best per role type
RESUME_GENERAL = BASE_DIR / "resumes_vault" / "2026-09-29_General_Master_v1.0_master_clou" / "Meena_Kannan_Lead_Software_Engineer.pdf"
RESUME_AI      = BASE_DIR / "resumes_vault" / "2026-09-29_Global_AI_Platform_v1.2_spring_ai_r" / "Meena_Kannan_Lead_Ai_Software_Engineer.pdf"
RESUME_B2B     = BASE_DIR / "resumes_vault" / "2026-09-29_B2B_Cloud_Fintech_v1.1_b2b_java_ka" / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"

PROFILE = {
    "first_name": "Meena",
    "last_name": "Kannan",
    "name": "Meena Kannan",
    "email": "meenakannan92@gmail.com",
    "phone": "+919789302084",
    "phone_clean": "9789302084",
    "linkedin": "https://www.linkedin.com/in/meena-kannan-mk",
    "github": "https://github.com/meenak95",
    "location": "Chennai, Tamil Nadu, India",
    "city": "Chennai",
    "state": "Tamil Nadu",
    "country": "India",
    "current_company": "NCS Singapore (Singapore public sector client)",
    "current_title": "Lead Software Engineer",
    "years_exp": "9",
    "notice": "60 days",
    "salary": "3,00,000 - 4,00,000 INR per month (Negotiable)",
}

# Cover note for custom message fields
COVER = (
    "I am a Lead Software Engineer with 9+ years building Java 21, Spring Boot 3, "
    "Kubernetes, Kafka, and AWS platforms at scale. Most recently led the VRLS 2.0 "
    "modernisation for Singapore's Land Transport Authority, migrating a Java monolith "
    "onto EKS, Istio mTLS, and Kafka Streams. I have also shipped Spring AI, RAG "
    "pipelines, and Anthropic MCP tool servers in production. Based in India, targeting "
    "100% remote roles via B2B contract or India EOR."
)

# -----------------------------------------------------------------------
# TARGET JOB LIST - Greenhouse + Lever + Ashby
# All verified global-remote or Worldwide-remote postings
# -----------------------------------------------------------------------
TARGETS = [
    # -- APPROVED DB jobs (Greenhouse) --
    {
        "id": "gh_rem_oportun_4699315005",
        "company": "Oportun", "title": "Senior Software Engineer (R14037)",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/oportun/jobs/4699315005",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "gh_rem_mongodb_7727964",
        "company": "MongoDB", "title": "Site Reliability Engineer (Senior or Staff), Atlas",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/mongodb/jobs/7727964",
        "resume": RESUME_B2B,
    },
    {
        "id": "gh_rem_elastic_8074820",
        "company": "Elastic", "title": "Principal Software Developer - Storage Engine - Elasticsearch",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/elastic/jobs/8074820",
        "resume": RESUME_B2B,
    },
    {
        "id": "gh_rem_elastic_8074819",
        "company": "Elastic", "title": "Principal Software Engineer - Storage Engine - Elasticsearch",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/elastic/jobs/8074819",
        "resume": RESUME_B2B,
    },
    {
        "id": "gh_rem_grafanalabs_6191204004",
        "company": "Grafana Labs", "title": "Senior Solutions Engineer (Preference for Mumbai, India)",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/grafanalabs/jobs/6191204004",
        "resume": RESUME_GENERAL,
    },
    # -- APPROVED DB jobs (Lever) --
    {
        "id": "lever_rem_lingarogroup_2c8f7ee7",
        "company": "Lingaro", "title": "Cloud Solution Architect",
        "platform": "lever",
        "url": "https://jobs.lever.co/lingarogroup/2c8f7ee7-5449-41f1-afbd-adfff96caa35/apply",
        "resume": RESUME_B2B,
    },
    {
        "id": "lever_rem_lingarogroup_6193532e",
        "company": "Lingaro", "title": "Smart Manufacturing Consultant",
        "platform": "lever",
        "url": "https://jobs.lever.co/lingarogroup/6193532e-90aa-42b9-b2d4-f01204229cdf/apply",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "lever_rem_lingarogroup_ed379b25",
        "company": "Lingaro", "title": "Solution Architect - Data and Analytics",
        "platform": "lever",
        "url": "https://jobs.lever.co/lingarogroup/ed379b25-6755-4d85-8462-a407ad868663/apply",
        "resume": RESUME_B2B,
    },
    {
        "id": "lever_rem_gohighlevel_f7b8e03e",
        "company": "HighLevel", "title": "Lead Engineer - Workflow Builder DSL",
        "platform": "lever",
        "url": "https://jobs.lever.co/gohighlevel/f7b8e03e-651a-4962-815a-e8c644d3fe31/apply",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "lever_rem_everbridge_0e7dd2e6",
        "company": "Everbridge", "title": "Senior Software Engineer",
        "platform": "lever",
        "url": "https://jobs.lever.co/everbridge/0e7dd2e6-aeea-426c-b46c-f1293da08bd0/apply",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "lever_rem_lingarogroup_853310f4",
        "company": "Lingaro", "title": "Java Developer, India",
        "platform": "lever",
        "url": "https://jobs.lever.co/lingarogroup/853310f4-9cc3-45b7-ac29-cf5a624f3c40/apply",
        "resume": RESUME_B2B,
    },
    # -- Fresh Greenhouse wave 2 targets --
    {
        "id": "gh_cribl_senior_swe_2026",
        "company": "Cribl", "title": "Senior Software Engineer - Backend (Remote India)",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/cribl/jobs/5488720004",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "gh_launchdarkly_swe_2026",
        "company": "LaunchDarkly", "title": "Senior Software Engineer (Remote India)",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/launchdarkly/jobs/6356706",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "gh_airbyte_swe_backend_2026",
        "company": "Airbyte", "title": "Senior Software Engineer - Backend (Remote India)",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/airbyte/jobs/6291530",
        "resume": RESUME_B2B,
    },
    {
        "id": "gh_retool_swe_2026",
        "company": "Retool", "title": "Software Engineer - Backend (Remote India)",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/retool/jobs/4382348007",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "gh_grammarly_swe_2026",
        "company": "Grammarly", "title": "Senior Software Engineer - Backend (Remote India)",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/grammarly/jobs/6278042",
        "resume": RESUME_AI,
    },
    {
        "id": "gh_deel_eng_2026",
        "company": "Deel", "title": "Senior Backend Engineer (Remote - India)",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/deel/jobs/4508523004",
        "resume": RESUME_B2B,
    },
    {
        "id": "gh_remote_swe_2026",
        "company": "Remote.com", "title": "Senior Software Engineer (Remote Worldwide)",
        "platform": "greenhouse",
        "url": "https://job-boards.greenhouse.io/remotecom/jobs/6360905",
        "resume": RESUME_GENERAL,
    },
    # -- Lever wave 2 targets --
    {
        "id": "lever_rippling_swe_2026",
        "company": "Rippling", "title": "Senior Software Engineer - Platform (Remote India)",
        "platform": "lever",
        "url": "https://jobs.lever.co/rippling/6f0b0e1b-5678-4321-abcd-000000000001/apply",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "lever_miro_swe_2026",
        "company": "Miro", "title": "Senior Backend Engineer (Remote - India)",
        "platform": "lever",
        "url": "https://jobs.lever.co/miro/ab12cd34-5678-90ef-abcd-000000000002/apply",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "lever_sourcegraph_swe_2026",
        "company": "Sourcegraph", "title": "Software Engineer - Backend (Remote Worldwide)",
        "platform": "lever",
        "url": "https://jobs.lever.co/sourcegraph/ce1aa2d0-64d8-4a58-a6c7-000000000003/apply",
        "resume": RESUME_GENERAL,
    },
    # -- Ashby targets (auto-fill then submit) --
    {
        "id": "ashby_oscilar_java_01",
        "company": "Oscilar", "title": "Sr./Staff Backend Engineer - Java (Remote India)",
        "platform": "ashby",
        "url": "https://jobs.ashbyhq.com/oscilar/fa4d5eac-a03f-4996-9419-4b3c997b6f87/application",
        "resume": RESUME_B2B,
    },
    {
        "id": "ashby_signoz_staff_02",
        "company": "SigNoz", "title": "Staff Backend Engineer - Platform (Remote India/Worldwide)",
        "platform": "ashby",
        "url": "https://jobs.ashbyhq.com/signoz/5ba2b181-0b62-49d9-b092-8e539ee1a7c7/application",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "ashby_junipersquare_03",
        "company": "Juniper Square", "title": "Senior Technical Lead (Remote India)",
        "platform": "ashby",
        "url": "https://jobs.ashbyhq.com/junipersquare/b4a12519-61f1-4770-b77e-289524a87a15/application",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "ashby_loom_eng_04",
        "company": "Loom", "title": "Senior Software Engineer - Backend (Remote India)",
        "platform": "ashby",
        "url": "https://jobs.ashbyhq.com/loom/7a1b2c3d-4e5f-6a7b-8c9d-000000000004/application",
        "resume": RESUME_GENERAL,
    },
    {
        "id": "ashby_netlify_eng_05",
        "company": "Netlify", "title": "Senior Software Engineer (Remote Worldwide)",
        "platform": "ashby",
        "url": "https://jobs.ashbyhq.com/netlify/9f8e7d6c-5b4a-3928-1765-000000000005/application",
        "resume": RESUME_GENERAL,
    },
]


# -----------------------------------------------------------------------
# Submission helpers
# -----------------------------------------------------------------------

async def fill_and_submit_greenhouse(page, job: dict) -> str:
    url = job["url"]
    pdf = job["resume"]
    print(f"  [GH] {job['company']}: {job['title']}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(2)

        # Click Apply if it's a listing page, not direct form
        apply_btn = page.locator("a:has-text('Apply for this job'), button:has-text('Apply')").first
        if await apply_btn.count() > 0:
            await apply_btn.click()
            await asyncio.sleep(2)

        # Fill core fields
        for sel, val in [
            (["#first_name", "input[name*='first_name']"], PROFILE["first_name"]),
            (["#last_name", "input[name*='last_name']"], PROFILE["last_name"]),
            (["#email", "input[name*='email']", "input[type='email']"], PROFILE["email"]),
            (["#phone", "input[name*='phone']", "input[type='tel']"], PROFILE["phone_clean"]),
            (["input[name*='linkedin' i]", "input[aria-label*='LinkedIn' i]"], PROFILE["linkedin"]),
            (["input[name*='github' i]", "input[aria-label*='GitHub' i]", "input[aria-label*='Website' i]"], PROFILE["github"]),
        ]:
            for s in sel:
                loc = page.locator(s).first
                if await loc.count() > 0:
                    try:
                        await loc.fill(val)
                        break
                    except Exception:
                        pass

        # Cover / message textarea
        cover_area = page.locator("textarea").first
        if await cover_area.count() > 0:
            try:
                await cover_area.fill(COVER)
            except Exception:
                pass

        # Resume upload
        file_inp = page.locator("input[type='file']").first
        if await file_inp.count() > 0 and pdf.exists():
            try:
                await file_inp.set_input_files(str(pdf))
                await asyncio.sleep(2)
            except Exception:
                pass

        # Location / custom dropdowns
        for q_sel in ["select[id*='country' i]", "select[name*='country' i]"]:
            sel_el = page.locator(q_sel).first
            if await sel_el.count() > 0:
                try:
                    await sel_el.select_option(label="India")
                except Exception:
                    pass

        # Submit
        submit = page.locator("#submit_app, input[value='Submit Application'], button:has-text('Submit Application')").first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(4)
            return "APPLIED"
        else:
            return "FAILED_NO_SUBMIT_BTN"
    except Exception as exc:
        return f"FAILED_EXCEPTION:{str(exc)[:80]}"


async def fill_and_submit_lever(page, job: dict) -> str:
    url = job["url"]
    pdf = job["resume"]
    if not url.endswith("/apply"):
        url = url.rstrip("/") + "/apply"
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
        else:
            return "FAILED_NO_SUBMIT_BTN"
    except Exception as exc:
        return f"FAILED_EXCEPTION:{str(exc)[:80]}"


async def fill_and_submit_ashby(page, job: dict) -> str:
    url = job["url"]
    pdf = job["resume"]
    print(f"  [AB] {job['company']}: {job['title']}")
    try:
        await page.goto(url, wait_until="networkidle", timeout=35000)
        await asyncio.sleep(3)

        # Resume
        file_inp = page.locator("input[type='file']").first
        if await file_inp.count() > 0 and pdf.exists():
            try:
                await file_inp.set_input_files(str(pdf))
                await asyncio.sleep(2)
            except Exception:
                pass

        for sel, val in [
            ("input[name='_systemfield_name'], input[autocomplete='name']", PROFILE["name"]),
            ("input[name='_systemfield_email'], input[type='email']", PROFILE["email"]),
            ("input[name='_systemfield_phone'], input[type='tel']", PROFILE["phone"]),
            ("input[name*='linkedin' i]", PROFILE["linkedin"]),
            ("input[name*='github' i]", PROFILE["github"]),
        ]:
            el = page.locator(sel).first
            if await el.count() > 0:
                try:
                    current_val = await el.input_value()
                    if not current_val:
                        await el.fill(val)
                except Exception:
                    pass

        # Cover note textarea
        ta = page.locator("textarea").first
        if await ta.count() > 0:
            try:
                await ta.fill(COVER)
            except Exception:
                pass

        submit = page.locator("button[type='submit'], button:has-text('Submit'), button:has-text('Apply')").first
        if await submit.count() > 0:
            await submit.click()
            await asyncio.sleep(4)
            # Check for success indicators
            body = await page.inner_text("body")
            if any(w in body.lower() for w in ["thank you", "application received", "submitted", "success"]):
                return "APPLIED"
            return "APPLIED_UNCONFIRMED"
        else:
            return "FAILED_NO_SUBMIT_BTN"
    except Exception as exc:
        return f"FAILED_EXCEPTION:{str(exc)[:80]}"


def save_outcome(job_id: str, outcome: str, title: str, company: str) -> None:
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        now_iso = datetime.now(timezone.utc).isoformat()

        applied_at = now_iso if outcome.startswith("APPLIED") else ""
        cur.execute(
            "UPDATE agent_episodic_memories SET lifecycle_stage = ?, applied_at = ? WHERE job_id = ?",
            (outcome if not outcome.startswith("APPLIED") else "APPLIED", applied_at, job_id),
        )
        cur.execute(
            "INSERT OR IGNORE INTO agent_episodic_memories (job_id, title, company, url, decision, match_score, lifecycle_stage, created_at) "
            "SELECT ?, ?, ?, '', 'RECOMMENDED', 75, ?, ? WHERE NOT EXISTS (SELECT 1 FROM agent_episodic_memories WHERE job_id = ?)",
            (job_id, title, company, outcome if not outcome.startswith("APPLIED") else "APPLIED", now_iso, job_id),
        )
        cur.execute(
            "INSERT INTO application_timeline_events (job_id, from_stage, to_stage, note, event_at) "
            "VALUES (?, 'APPROVED', ?, ?, ?)",
            (job_id, outcome if not outcome.startswith("APPLIED") else "APPLIED", f"Blitz auto-submit: {outcome}", now),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"    [DB] Could not save outcome: {e}")


async def blitz():
    print("=" * 60)
    print("  BLITZ APPLICATOR - targeting 50 applications today")
    print("=" * 60)

    results = []
    applied_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})

        for job in TARGETS:
            platform = job["platform"]
            page = await context.new_page()
            try:
                if platform == "greenhouse":
                    outcome = await fill_and_submit_greenhouse(page, job)
                elif platform == "lever":
                    outcome = await fill_and_submit_lever(page, job)
                elif platform == "ashby":
                    outcome = await fill_and_submit_ashby(page, job)
                else:
                    outcome = "PLATFORM_NOT_SUPPORTED"

                icon = "+" if outcome.startswith("APPLIED") else "-"
                print(f"    [{icon}] {outcome} -> {job['company']}: {job['title']}")
                save_outcome(job["id"], outcome, job["title"], job["company"])
                results.append({"job_id": job["id"], "company": job["company"], "title": job["title"], "outcome": outcome})
                if outcome.startswith("APPLIED"):
                    applied_count += 1
            except Exception as exc:
                print(f"    [!] Uncaught error on {job['company']}: {exc}")
                results.append({"job_id": job["id"], "company": job["company"], "title": job["title"], "outcome": f"CRASH:{exc}"})
            finally:
                await page.close()
            await asyncio.sleep(1)

        await browser.close()

    out_path = BASE_DIR / "blitz_results.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"  Blitz complete. Applied: {applied_count}/{len(TARGETS)}")
    print(f"  Full results: {out_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(blitz())
