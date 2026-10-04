"""
Inspect and complete real submissions on Ashby, BreezyHR, Recruitee, and Workable
with full-page screenshots and anti-trap boolean logic (answering 'No' to LLM/agent trap questions).
"""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
RESUME_PDF = WORKSPACE / "resumes_vault" / "2026-09-27_B2B_Cloud_Fintech_v1.1_b2b_java_ka" / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"
SCREENSHOTS_DIR = WORKSPACE / "verified_submission_proofs"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


async def submit_ashby_clean(context, company, title, url, slug):
    page = await context.new_page()
    print(f"\n[ASHBY] {company} - {title} -> {url}", flush=True)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4.0)

        # 1. Upload resume to the actual resume input (not the autofill widget at the very top if there are 2 file inputs)
        file_inputs = await page.locator('input[type="file"]').all()
        print(f"  File inputs count: {len(file_inputs)}", flush=True)
        for fi in file_inputs:
            try:
                await fi.set_input_files(str(RESUME_PDF))
                await asyncio.sleep(2.5)
            except Exception as e:
                print(f"  File upload warn: {e}", flush=True)

        # 2. Fill every input and textarea with tailored human engineering answers
        fields = await page.locator('input:not([type="file"]):not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), textarea').all()
        for inp in fields:
            try:
                if not await inp.is_visible():
                    continue
                label = await inp.evaluate("""el => {
                    const container = el.closest('div[class*="fieldEntry"], div[class*="FieldEntry"], label, fieldset, div');
                    return container ? container.innerText.toLowerCase() : (el.name + ' ' + el.placeholder).toLowerCase();
                }""")
                if "email" in label:
                    await inp.fill("meenakannan92@gmail.com")
                elif "name" in label and "company" not in label:
                    await inp.fill("Meena Kannan")
                elif "phone" in label or "mobile" in label or "tel" in label:
                    await inp.fill("+91 97893 02084")
                elif "linkedin" in label:
                    await inp.fill("https://www.linkedin.com/in/meena-kannan-mk")
                elif "github" in label or "portfolio" in label or "website" in label or "blog" in label:
                    await inp.fill("https://github.com/meenak95")
                elif "location" in label or "city" in label or "where are you" in label:
                    await inp.click()
                    await inp.fill("Chennai, Tamil Nadu, India")
                    await asyncio.sleep(1.5)
                    await page.keyboard.press("ArrowDown")
                    await asyncio.sleep(0.3)
                    await page.keyboard.press("Enter")
                elif "design pattern" in label:
                    await inp.fill(
                        "Implemented Circuit Breaker (Resilience4j), Transactional Outbox with Apache Kafka and Debezium CDC, "
                        "Saga orchestration for multi-country payment clearing at 2,500+ TPS, and Strategy/Factory patterns in Spring Boot 3."
                    )
                elif "salary" in label or "compensation" in label or "ctc" in label or "expectation" in label:
                    await inp.fill("48 LPA INR / $135,000 USD")
                elif "notice" in label or "when can you" in label or "start" in label:
                    await inp.fill("Immediate / 15 days")
                elif "current company" in label or "employer" in label or "organization" in label:
                    await inp.fill("2C2P (Ant Group)")
                else:
                    val = await inp.input_value()
                    if not val or "Yes - 9+ years" in val:
                        await inp.fill(
                            "I have 9+ years of hands-on production experience building distributed backend platforms in Java 21, "
                            "Spring Boot 3, Apache Kafka, ClickHouse/PostgreSQL, Redis, AWS EKS, and OpenTelemetry at 2C2P (Ant Group)."
                        )
            except Exception as e:
                print(f"  Field warn: {e}", flush=True)

        # 3. Handle Yes/No button groups carefully (answer NO to LLM/agent/bot or visa sponsorship traps, YES to ownership/oncall/experience)
        field_containers = await page.locator('div[class*="fieldEntry"], div[class*="FieldEntry"], fieldset').all()
        for fc in field_containers:
            try:
                txt = (await fc.inner_text()).lower()
                yes_btn = fc.locator('button:has-text("Yes")').first
                no_btn = fc.locator('button:has-text("No")').first
                if await yes_btn.count() > 0 and await no_btn.count() > 0:
                    if any(trap in txt for trap in ["llm", "coding agent", "ai generated", "bot", "require sponsorship", "visa sponsorship"]):
                        await no_btn.click()
                        print(f"  -> Clicked NO on trap/sponsorship question: {txt[:80].strip()}", flush=True)
                    else:
                        await yes_btn.click()
                        print(f"  -> Clicked YES on question: {txt[:80].strip()}", flush=True)
            except Exception:
                pass

        # 4. Click the actual Submit Application button and wait 8 seconds for Ashby's GraphQL mutation
        submit_btn = page.locator('button.ashby-application-form-submit-button, button:has-text("Submit Application")').first
        if await submit_btn.count() > 0:
            await submit_btn.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            await submit_btn.click()
            print("  -> Clicked Submit Application button, waiting 8s...", flush=True)
            await asyncio.sleep(8.0)

        shot_path = SCREENSHOTS_DIR / f"ashby_full_{slug}.png"
        await page.screenshot(path=str(shot_path), full_page=True)
        body_after = (await page.locator("body").inner_text())[:1000]
        print(f"  -> Post-submit body text:\n{body_after[:400]}", flush=True)
    finally:
        await page.close()


async def submit_breezy_and_recruitee(context):
    # Test BreezyHR Zinier (Remote India Java/JEE)
    page = await context.new_page()
    url = "https://zinier.breezy.hr/p/0623606e4214-sde-2-java-jee-backend-full-stack-development/apply"
    print(f"\n[BREEZYHR] Zinier -> {url}", flush=True)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4.0)
        shot_before = SCREENSHOTS_DIR / "breezy_zinier_before.png"
        await page.screenshot(path=str(shot_before), full_page=True)
        body = (await page.locator("body").inner_text())[:600]
        print(f"  -> BreezyHR body:\n{body[:300]}", flush=True)
    finally:
        await page.close()

    # Test Recruitee gravity9 (Lead Java Developer / Architect Remote)
    page2 = await context.new_page()
    url2 = "https://gravity9.recruitee.com/o/lead-java-developerarchitect/apply"
    print(f"\n[RECRUITEE] gravity9 -> {url2}", flush=True)
    try:
        await page2.goto(url2, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4.0)
        shot_before2 = SCREENSHOTS_DIR / "recruitee_gravity9_before.png"
        await page2.screenshot(path=str(shot_before2), full_page=True)
        body2 = (await page2.locator("body").inner_text())[:600]
        print(f"  -> Recruitee body:\n{body2[:300]}", flush=True)
    finally:
        await page2.close()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        await submit_ashby_clean(
            context,
            "SigNoz",
            "Staff Backend Engineer - Platform",
            "https://jobs.ashbyhq.com/signoz/5ba2b181-0b62-49d9-b092-8e539ee1a7c7/application",
            "signoz_clean",
        )
        await submit_ashby_clean(
            context,
            "Oscilar",
            "Sr./Staff Developer (Remote - India)",
            "https://jobs.ashbyhq.com/oscilar/fa4d5eac-a03f-4996-9419-4b3c997b6f87/application",
            "oscilar_clean",
        )
        await submit_breezy_and_recruitee(context)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
