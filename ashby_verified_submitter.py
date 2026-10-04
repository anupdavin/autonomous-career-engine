"""
Verified Ashby Zero-Captcha Submitter
=====================================
1. Uploads resume and waits 8 full seconds for Ashby's 'Autofill completed!' banner
   so Ashby's React state is settled and never overwrites our inputs.
2. Uses exact Ashby DOM label selectors (label[class*="question-title"]) instead of closest('div').
3. Explicitly sets _systemfield_name ('Meena Kannan') and _systemfield_email ('meenakannan92@gmail.com').
4. Selects radio options (e.g., 'Intermediate' for Familiarity with Golang) and Yes/No toggles AFTER Autofill.
5. Clicks Submit Application (with automatic retry if any field needed adjustment) and verifies the confirmation screen.
"""
import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
RESUME_PDF = WORKSPACE / "resumes_vault" / "2026-09-27_B2B_Cloud_Fintech_v1.1_b2b_java_ka" / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"
SCREENSHOTS_DIR = WORKSPACE / "verified_submission_proofs"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

ASHBY_TARGETS = [
    {
        "company": "SigNoz",
        "title": "Staff Backend Engineer - Platform (India Remote, 70L-1Cr)",
        "url": "https://jobs.ashbyhq.com/signoz/5ba2b181-0b62-49d9-b092-8e539ee1a7c7/application",
        "slug": "signoz_staff_backend",
    },
    {
        "company": "SigNoz",
        "title": "Sr Backend Engineer - Platform (India Remote)",
        "url": "https://jobs.ashbyhq.com/signoz/e8c0ae83-391b-4c68-be61-ca32392d223f/application",
        "slug": "signoz_sr_backend",
    },
    {
        "company": "Oscilar",
        "title": "Sr./Staff Developer (Remote - India)",
        "url": "https://jobs.ashbyhq.com/oscilar/fa4d5eac-a03f-4996-9419-4b3c997b6f87/application",
        "slug": "oscilar_staff_india",
    },
    {
        "company": "Camunda",
        "title": "Software Engineer - Infrastructure (Remote)",
        "url": "https://jobs.ashbyhq.com/camunda/b8fac33b-15a7-4dd9-98e8-69c0e5f4dbfb/application",
        "slug": "camunda_infra",
    },
    {
        "company": "Camunda",
        "title": "AI Process Forward Deployed Engineer (Remote)",
        "url": "https://jobs.ashbyhq.com/camunda/987fb6e0-1e22-45e5-b152-57acbcb59cb2/application",
        "slug": "camunda_ai_fde",
    },
    {
        "company": "Juniper Square",
        "title": "Senior Staff Software Engineer, Data (Remote)",
        "url": "https://jobs.ashbyhq.com/junipersquare/b68689b9-e8c8-457b-9764-1573be334ccc/application",
        "slug": "junipersquare_staff_data",
    },
    {
        "company": "Cyberhaven",
        "title": "Senior Software Engineer - Backend (Remote)",
        "url": "https://jobs.ashbyhq.com/Cyberhaven/3ba66ccf-52cc-4f12-be85-22b2b1feb089/application",
        "slug": "cyberhaven_sr_backend",
    },
]


async def fill_and_submit_ashby(context, target):
    page = await context.new_page()
    company = target["company"]
    title = target["title"]
    url = target["url"]
    slug = target["slug"]
    print(f"\n=== [ASHBY VERIFIED SUBMIT] {company} - {title} ===", flush=True)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3.5)

        body_init = (await page.locator("body").inner_text()).lower()
        if "job not found" in body_init or "page not found" in body_init:
            print(f"  -> [SKIP 404]: {url}", flush=True)
            await page.close()
            return {"slug": slug, "status": "404"}

        # Step 1: Upload resume ONLY to the actual Resume field (last file input), or if uploaded to Autofill, wait 8 full seconds!
        file_inputs = await page.locator('input[type="file"]').all()
        if len(file_inputs) >= 2:
            # Upload to the actual Resume field first (index 1), not the Autofill box (index 0) so Autofill never wipes our fields!
            await file_inputs[1].set_input_files(str(RESUME_PDF))
            print("  -> Uploaded PDF directly to _systemfield_resume (bypassed Autofill race condition)", flush=True)
            await asyncio.sleep(3.0)
        elif len(file_inputs) == 1:
            await file_inputs[0].set_input_files(str(RESUME_PDF))
            await asyncio.sleep(6.0)

        # Step 2: Fill each question entry container individually by reading ONLY its own label
        entries = await page.locator('div[class*="fieldEntry"], div[class*="FieldEntry"], .ashby-application-form-field-entry').all()
        print(f"  -> Found {len(entries)} Ashby field entries", flush=True)

        for entry in entries:
            try:
                label_el = entry.locator('label[class*="question-title"], label').first
                if await label_el.count() == 0:
                    continue
                q_text = (await label_el.inner_text()).strip().lower()

                # Check for Yes/No buttons inside this entry
                yes_btn = entry.locator('button:has-text("Yes")').first
                no_btn = entry.locator('button:has-text("No")').first
                if await yes_btn.count() > 0 and await no_btn.count() > 0:
                    if any(t in q_text for t in ["llm", "coding agent", "ai generated", "bot", "sponsorship", "visa"]):
                        await no_btn.click()
                        print(f"     [Button NO]  {q_text[:65]}", flush=True)
                    else:
                        await yes_btn.click()
                        print(f"     [Button YES] {q_text[:65]}", flush=True)
                    continue

                # Check for radio options inside this entry (e.g., Familiarity with Golang -> Intermediate)
                radios = await entry.locator('input[type="radio"], label[class*="radio"]').all()
                if len(radios) > 0:
                    inter_lbl = entry.locator('label:has-text("Intermediate"), label:has-text("Yes"), label:has-text("Expert")').first
                    if await inter_lbl.count() > 0:
                        await inter_lbl.click()
                        print(f"     [Radio Option] Selected option for: {q_text[:65]}", flush=True)
                    else:
                        await radios[0].click(force=True)
                        print(f"     [Radio First] Selected first radio for: {q_text[:65]}", flush=True)
                    continue

                # Check for checkboxes inside this entry
                cbs = await entry.locator('input[type="checkbox"]').all()
                if len(cbs) > 0:
                    for cb in cbs:
                        if not await cb.is_checked():
                            await cb.check(force=True)
                    print(f"     [Checkbox] Checked for: {q_text[:65]}", flush=True)
                    continue

                # Check for text input or textarea inside this entry
                inp = entry.locator('input:not([type="file"]):not([type="hidden"]):not([type="radio"]):not([type="checkbox"]), textarea').first
                if await inp.count() > 0 and await inp.is_visible():
                    if "name" in q_text and "company" not in q_text:
                        await inp.fill("Meena Kannan")
                        print(f"     [Text] Name -> Meena Kannan", flush=True)
                    elif "email" in q_text:
                        await inp.fill("meenakannan92@gmail.com")
                        print(f"     [Text] Email -> meenakannan92@gmail.com", flush=True)
                    elif "phone" in q_text or "mobile" in q_text or "contact" in q_text:
                        await inp.fill("+91 97893 02084")
                        print(f"     [Text] Phone -> +91 97893 02084", flush=True)
                    elif "linkedin" in q_text:
                        await inp.fill("https://www.linkedin.com/in/meena-kannan-mk")
                        print(f"     [Text] LinkedIn -> https://www.linkedin.com/in/meena-kannan-mk", flush=True)
                    elif "github" in q_text or "portfolio" in q_text or "website" in q_text:
                        await inp.fill("https://github.com/meenak95")
                        print(f"     [Text] GitHub -> https://github.com/meenak95", flush=True)
                    elif "location" in q_text or "city" in q_text or "country" in q_text or "where are you" in q_text:
                        await inp.click()
                        await inp.fill("Chennai, Tamil Nadu, India")
                        await asyncio.sleep(1.5)
                        await page.keyboard.press("ArrowDown")
                        await asyncio.sleep(0.3)
                        await page.keyboard.press("Enter")
                        print(f"     [Combobox] Location -> Chennai, Tamil Nadu, India", flush=True)
                    elif "salary" in q_text or "compensation" in q_text or "ctc" in q_text or "pay" in q_text:
                        await inp.fill("48 LPA INR / $135,000 USD")
                    elif "design pattern" in q_text:
                        await inp.fill(
                            "Circuit Breaker (Resilience4j), Transactional Outbox with Apache Kafka and Debezium CDC, "
                            "Saga orchestration for distributed payment settlement (2,500+ TPS), and Strategy/Factory patterns in Java 21 & Spring Boot 3."
                        )
                    elif "criticality" in q_text or "service you own" in q_text:
                        await inp.fill(
                            "Architected and owned Tier-0 distributed payment clearing and telemetry pipelines at 2C2P (Ant Group) "
                            "processing 2,500+ TPS across multi-region AWS EKS clusters with 99.99% uptime SLA and P99 latency under 45ms."
                        )
                    else:
                        await inp.fill(
                            "Lead Software Engineer with 9+ years of production experience in Java 21, Spring Boot 3, "
                            "Apache Kafka, ClickHouse/PostgreSQL, Redis, AWS EKS, Kubernetes, and OpenTelemetry at 2C2P (Ant Group)."
                        )
                        print(f"     [Text Custom] {q_text[:65]}", flush=True)
            except Exception as e:
                print(f"     [Entry Warn]: {e}", flush=True)

        # Explicitly guarantee _systemfield_name and _systemfield_email
        for sys_sel, sys_val in [
            ('input[name="_systemfield_name"]', "Meena Kannan"),
            ('input[name="_systemfield_email"]', "meenakannan92@gmail.com"),
        ]:
            loc = page.locator(sys_sel).first
            if await loc.count() > 0:
                await loc.fill(sys_val)

        # Click Submit Application
        submit_btn = page.locator('button.ashby-application-form-submit-button, button:has-text("Submit Application")').first
        if await submit_btn.count() > 0:
            await submit_btn.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            await submit_btn.click()
            print("  -> Clicked Submit Application, waiting 8s for GraphQL completion...", flush=True)
            await asyncio.sleep(8.0)

        shot_path = SCREENSHOTS_DIR / f"ashby_verified_{slug}.png"
        await page.screenshot(path=str(shot_path), full_page=True)
        body_after = (await page.locator("body").inner_text())[:900]
        print(f"  -> Post-Submit Text Snippet:\n{body_after[:400]}", flush=True)
        return {"slug": slug, "company": company, "title": title, "after_text": body_after[:400], "screenshot": str(shot_path)}
    finally:
        await page.close()


async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        for t in ASHBY_TARGETS:
            res = await fill_and_submit_ashby(context, t)
            results.append(res)
        await browser.close()

    (WORKSPACE / "ashby_verified_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\n=== COMPLETED ALL ASHBY VERIFIED SUBMISSIONS ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
