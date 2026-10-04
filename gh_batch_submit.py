"""
gh_batch_submit.py - Submit all APPROVED Greenhouse jobs with real job IDs.
Uses the corrected flow: navigate listing page -> find Apply -> fill -> submit.
"""
import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
DB_PATH = BASE_DIR / "oracle_ai_local_mirror.db"
RESUME_GENERAL = BASE_DIR / "resumes_vault" / "2026-09-29_General_Master_v1.0_master_clou" / "Meena_Kannan_Lead_Software_Engineer.pdf"
RESUME_B2B = BASE_DIR / "resumes_vault" / "2026-09-29_B2B_Cloud_Fintech_v1.1_b2b_java_ka" / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"

COVER = (
    "I am a Lead Software Engineer with 9 years building Java 21, Spring Boot 3, "
    "Kubernetes, Kafka, and AWS platforms at scale. Most recently I led the VRLS 2.0 "
    "modernisation for Singapore's Land Transport Authority, migrating a Java monolith "
    "onto EKS, Istio mTLS, and Kafka Streams. I also ship Spring AI, RAG pipelines, "
    "and MCP tool servers in production Java services. Based in India, 100% remote."
)

PROFILE = {
    "first_name": "Meena", "last_name": "Kannan", "name": "Meena Kannan",
    "email": "meenakannan92@gmail.com", "phone_clean": "9789302084",
    "linkedin": "https://www.linkedin.com/in/meena-kannan-mk",
    "github": "https://github.com/meenak95",
    "current_company": "NCS Singapore",
}

# Pull APPROVED Greenhouse jobs with real URLs from DB
conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""
    SELECT job_id, title, company, url, match_score
    FROM agent_episodic_memories
    WHERE lifecycle_stage = 'APPROVED'
    AND url LIKE '%greenhouse.io%'
    AND url LIKE '%/jobs/%'
    AND job_id NOT IN (
        SELECT DISTINCT job_id FROM application_timeline_events WHERE to_stage = 'APPLIED'
    )
    ORDER BY match_score DESC
""")
GH_TARGETS = [dict(r) for r in cur.fetchall()]
conn.close()

print(f"Greenhouse targets to submit: {len(GH_TARGETS)}")
for t in GH_TARGETS:
    print(f"  {t['match_score']} | {t['title'][:50]} @ {t['company']}")


def save_outcome(job_id: str, outcome: str) -> None:
    try:
        conn2 = sqlite3.connect(str(DB_PATH))
        cur2 = conn2.cursor()
        now = datetime.now(timezone.utc).isoformat()
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        stage = "APPLIED" if outcome.startswith("APPLIED") else outcome
        applied_at = now if stage == "APPLIED" else ""
        cur2.execute("UPDATE agent_episodic_memories SET lifecycle_stage=?, applied_at=? WHERE job_id=?",
                     (stage, applied_at, job_id))
        cur2.execute("INSERT INTO application_timeline_events (job_id, from_stage, to_stage, note, event_at) "
                     "VALUES (?, 'APPROVED', ?, ?, ?)",
                     (job_id, stage, f"gh_batch_submit: {outcome}", now_str))
        conn2.commit()
        conn2.close()
    except Exception as e:
        print(f"    [DB] {e}")


async def submit_gh(page, job: dict) -> str:
    url = job["url"]
    pdf = RESUME_B2B if any(k in job["title"].lower() for k in ("architect", "staff", "principal", "data", "b2b")) else RESUME_GENERAL
    print(f"\n  [GH] {job['company']}: {job['title']}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(2)

        # Look for Apply button - may open a popup or navigate to embed
        apply_btn = page.locator("a:has-text('Apply for this job'), a:has-text('Apply Now'), button:has-text('Apply')").first
        if await apply_btn.count() > 0:
            href = await apply_btn.get_attribute("href") or ""
            if href and href.startswith("http"):
                # Direct link - navigate to it
                await page.goto(href, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                form_page = page
            else:
                try:
                    async with page.expect_popup(timeout=5000) as popup_info:
                        await apply_btn.click()
                    form_page = await popup_info.value
                    await form_page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(2)
                except Exception:
                    await apply_btn.click()
                    await asyncio.sleep(2)
                    form_page = page
        else:
            form_page = page

        # Fill fields
        for sel_list, val in [
            (["#first_name", "input[name*='first_name']", "input[autocomplete='given-name']"], PROFILE["first_name"]),
            (["#last_name", "input[name*='last_name']", "input[autocomplete='family-name']"], PROFILE["last_name"]),
            (["#email", "input[type='email']", "input[name*='email']"], PROFILE["email"]),
            (["#phone", "input[type='tel']", "input[name*='phone']"], PROFILE["phone_clean"]),
            (["input[name*='linkedin' i]", "input[aria-label*='LinkedIn' i]"], PROFILE["linkedin"]),
            (["input[name*='github' i]", "input[aria-label*='GitHub' i]", "input[aria-label*='Website' i]"], PROFILE["github"]),
        ]:
            for s in sel_list:
                loc = form_page.locator(s).first
                if await loc.count() > 0:
                    try:
                        await loc.fill(val)
                        break
                    except Exception:
                        pass

        # Cover note
        ta = form_page.locator("textarea").first
        if await ta.count() > 0:
            try:
                await ta.fill(COVER)
            except Exception:
                pass

        # Resume upload
        file_inp = form_page.locator("input[type='file']").first
        if await file_inp.count() > 0 and pdf.exists():
            try:
                await file_inp.set_input_files(str(pdf))
                await asyncio.sleep(2)
            except Exception:
                pass

        # Country dropdown
        for csel in ["select[id*='country' i]", "select[name*='country' i]"]:
            sel_el = form_page.locator(csel).first
            if await sel_el.count() > 0:
                try:
                    await sel_el.select_option(label="India")
                except Exception:
                    pass

        # Submit
        submit = form_page.locator(
            "#submit_app, input[value='Submit Application'], button:has-text('Submit Application'), button[type='submit']"
        ).locator("visible=true").first
        if await submit.count() > 0:
            await submit.click()
            try:
                # Wait for confirmation text or #application_confirmation
                await form_page.wait_for_selector(
                    "text=Application Submitted, text=Thank you for applying, #application_confirmation, h1:has-text('Thank You')",
                    timeout=8000
                )
                return "APPLIED"
            except:
                return "FAILED_NO_CONFIRMATION"
        return "FAILED_NO_SUBMIT_BTN"
    except Exception as exc:
        return f"FAILED:{str(exc)[:80]}"


async def run():
    applied = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        for job in GH_TARGETS:
            page = await context.new_page()
            try:
                outcome = await submit_gh(page, job)
                icon = "+" if outcome.startswith("APPLIED") else "-"
                print(f"    [{icon}] {outcome}")
                save_outcome(job["job_id"], outcome)
                if outcome.startswith("APPLIED"):
                    applied += 1
            except Exception as exc:
                print(f"    [!] Crash: {exc}")
            finally:
                await page.close()
            await asyncio.sleep(1)
        await browser.close()
    print(f"\nTotal applied this run: {applied}/{len(GH_TARGETS)}")


if __name__ == "__main__":
    asyncio.run(run())
