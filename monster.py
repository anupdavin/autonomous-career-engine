import asyncio
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright
import os

BASE_DIR = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
DB_PATH = BASE_DIR / "oracle_ai_local_mirror.db"
PYTHON_BIN = r"C:\Users\MeenaDavin\AppData\Local\Programs\Python\Python312\python.exe"
SALARY = "3,00,000 - 4,00,000 INR per month (Negotiable)"
NOTICE = "60 days"

# --- ADAPTIVE AGENT MEMORY ---
# Emulates Andrew Ng's reflection pattern by maintaining a runtime memory 
# of failures and deduplicating at the semantic level (Company + Core Title)
class AdaptiveAgentMemory:
    def __init__(self):
        self.failed_strategies = {}
        self.applied_signatures = set()
        
    def load_historical_memory(self, cur):
        # Load past applied jobs to build deduplication signatures
        cur.execute("SELECT company, title FROM agent_episodic_memories WHERE lifecycle_stage IN ('APPLIED', 'REJECTED')")
        for row in cur.fetchall():
            self.applied_signatures.add(self._get_signature(row['company'], row['title']))
            
    def _get_signature(self, company, title):
        # Normalizes "Senior Backend Engineer (R14037)" to "senior backend engineer"
        base_title = title.lower().split('(')[0].split('[')[0].strip()
        return f"{company.lower().strip()}_{base_title}"
        
    def is_duplicate(self, company, title):
        sig = self._get_signature(company, title)
        return sig in self.applied_signatures
        
    def record_success(self, company, title):
        self.applied_signatures.add(self._get_signature(company, title))

agent_memory = AdaptiveAgentMemory()

async def auto_apply_to_job(job, context, cur, conn):
    job_id = job["job_id"]
    url = job["url"]
    title = job["title"]
    company = job["company"]
    
    print(f"\n--> [MONSTER/ADAPTIVE] Evaluating {company}: {title}")
    
    # 1. Deduplication Reflection
    if agent_memory.is_duplicate(company, title):
        print(f"    [!] Reflection: Semantic duplicate detected for {company} / {title}. Skipping to prevent spam.")
        cur.execute("UPDATE agent_episodic_memories SET lifecycle_stage = 'DUPLICATE_SKIPPED' WHERE job_id = ?", (job_id,))
        conn.commit()
        return False
    
    pdf_path = BASE_DIR / "application_drafts" / "2026-09-28_meena_master_resume_candidate_review.md" 
    pdf_pdf = BASE_DIR / "application_drafts" / "2026-09-28_meena_kannan_eltropy_resume.pdf"
    if pdf_pdf.exists(): pdf_path = pdf_pdf

    try:
        page = await context.new_page()
        
        if "greenhouse.io" in url or "lever.co" in url:
            if "lever.co" in url and not url.endswith("/apply"):
                url = url.rstrip("/") + "/apply"
                
            print(f"    [*] Navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3)
            
            if "greenhouse.io" in url:
                apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply')").first
                if await apply_btn.count() > 0: await apply_btn.click()
            
            # 2. Adaptive Selectors (Self-Healing Fallbacks)
            fill_success = False
            for selector in ["input[name*='first_name']", "#first_name", "input[name='name']"]:
                try: 
                    if await page.locator(selector).count() > 0:
                        await page.locator(selector).first.fill("Meena Kannan")
                        fill_success = True
                        break
                except: pass
                
            try: await page.locator("input[name*='last_name'], #last_name").first.fill("Kannan")
            except: pass
            try: await page.locator("input[name*='email'], #email").first.fill("meenakannan92@gmail.com")
            except: pass
            try: await page.locator("input[name*='phone'], #phone").first.fill("+919789302084")
            except: pass
                
            if pdf_path.exists():
                try: await page.locator("input[type='file']").first.set_input_files(str(pdf_path))
                except: pass
            
            custom_fields = await page.locator("div.field, li.application-question, div.application-question, .custom-question").all()
            for field in custom_fields:
                try:
                    text = (await field.inner_text()).lower()
                    input_loc = field.locator("input[type='text'], textarea, select")
                    if await input_loc.count() > 0:
                        target = input_loc.first
                        tag = await target.evaluate("el => el.tagName")
                        
                        val = ""
                        if "salary" in text or "compensation" in text: val = SALARY
                        elif "notice" in text: val = NOTICE
                        elif "location" in text or "city" in text: val = "Chennai, Tamil Nadu, India"
                        elif "country" in text: val = "India"
                        elif "ai" in text or "tools" in text: val = "Cursor, GitHub Copilot, Claude 3.5 Sonnet, ChatGPT"
                        elif "prior employment" in text or "relatives" in text or "family" in text or "sponsor" in text: val = "No"
                        
                        if val:
                            if tag == "SELECT":
                                try: await target.select_option(label=val)
                                except: pass
                            else:
                                await target.fill(val)
                except: continue

            # 3. Action Execution
            submit_btn = page.locator("#submit_app, button:has-text('Submit Application'), button.postings-btn[data-qa='btn-submit']")
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
                await page.wait_for_timeout(5000)
                print(f"    [+] Submitted {company}")
                agent_memory.record_success(company, title)
                return 'APPLIED'
            else:
                print(f"    [-] Reflection: Could not find submit button for {company}. Capturing failure context.")
                return 'FAILED_AUTOMATION'
        else:
            print(f"    [!] Reflection: URL schema not natively supported by current Playwright tools: {url}")
            return 'FAILED_UNSUPPORTED_ATS'

    except Exception as e:
        # 4. Agentic Failure Logging
        error_sig = str(e).split('\n')[0][:100]
        print(f"    [x] Reflection: Execution failed on {company}. Error: {error_sig}")
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        cur.execute("INSERT INTO application_timeline_events (job_id, from_stage, to_stage, note, event_at) VALUES (?, ?, ?, ?, ?)", 
                   (job_id, 'SHORTLISTED', 'FAILED_AUTOMATION', error_sig, now_str))
        conn.commit()
        return 'FAILED_AUTOMATION'
    finally:
        await page.close()

async def monster_loop():
    print("==================================================")
    print("   ADAPTIVE MONSTER DAEMON: SELF-LEARNING MODE    ")
    print("==================================================")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        
        while True:
            print("\n[MONSTER] Waking up. Triggering discovery phase...")
            try: subprocess.run([PYTHON_BIN, "scheduler_24_7.py", "--once"], check=True)
            except Exception as e: print(f"[MONSTER] Discovery phase hit snag: {e}")

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # Initialize historical memory for deduplication
            agent_memory.load_historical_memory(cur)
            
            cur.execute("""
                SELECT job_id, title, company, url, match_score 
                FROM agent_episodic_memories 
                WHERE match_score >= 40 
                  AND lifecycle_stage = 'APPROVED'
                  AND (url LIKE '%greenhouse.io%' OR url LIKE '%lever.co%')
            """)
            targets = cur.fetchall()
            
            if not targets:
                print("[MONSTER] No viable fresh targets found. Resting for 15 minutes...")
            else:
                print(f"[MONSTER] Assessing {len(targets)} targets with adaptive logic...")
                for row in targets:
                    job = dict(row)
                    outcome = await auto_apply_to_job(job, context, cur, conn)
                    if outcome:
                        cur.execute("UPDATE agent_episodic_memories SET lifecycle_stage = ? WHERE job_id = ?", (outcome, job['job_id']))
                        conn.commit()
            
            conn.close()
            print("[MONSTER] Cycle complete. Memory committed. Digestion period: 15 minutes...")
            await asyncio.sleep(900)

if __name__ == "__main__":
    asyncio.run(monster_loop())
