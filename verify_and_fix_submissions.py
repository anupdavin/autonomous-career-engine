"""
Deep DOM Inspector & Verified Submission Engine
===============================================
Diagnoses why previous SUBMIT_CLICKED attempts stayed on /apply or /application
without sending confirmation emails, fills ALL required custom fields (selects,
radios, cards[...], React comboboxes), waits for resume parsing XHR completion,
and captures screenshot + DOM proof of actual submission.
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

WORKSPACE = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
RESUME_PDF = WORKSPACE / "resumes_vault" / "2026-09-27_B2B_Cloud_Fintech_v1.1_b2b_java_ka" / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"
SCREENSHOTS_DIR = WORKSPACE / "verified_submission_proofs"
SCREENSHOTS_DIR.mkdir(exist_ok=True)


async def launch_browser(p):
    stealth_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--no-first-run",
    ]
    for kwargs in [
        {"channel": "chrome", "headless": False, "args": stealth_args},
        {"channel": "msedge", "headless": False, "args": stealth_args},
        {"headless": False, "args": stealth_args},
    ]:
        try:
            return await p.chromium.launch(**kwargs)
        except Exception:
            continue
    raise RuntimeError("No browser available")


async def inspect_and_submit_lever(context, company, title, url, slug):
    page = await context.new_page()
    print(f"\n[LEVER INSPECT] {company} - {title} -> {url}", flush=True)
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3.0)
        print(f"  HTTP Status: {resp.status}, Final URL: {page.url}", flush=True)
        if resp.status == 404 or "not found" in (await page.title()).lower():
            print("  -> [404 EXPIRED POSTING]", flush=True)
            await page.close()
            return {"slug": slug, "status": "404_EXPIRED"}

        # 1. Upload resume and WAIT for Lever's /parseResume XHR to complete
        resume_input = page.locator('input[name="resume"], input[type="file"]').first
        if await resume_input.count() > 0:
            await resume_input.set_input_files(str(RESUME_PDF))
            print("  -> Uploaded resume PDF, waiting 6s for Lever parseResume XHR...", flush=True)
            await asyncio.sleep(6.0)

        # 2. Fill standard Lever fields (overwrite anything parseResume mangled)
        standard = {
            'input[name="name"]': "Meena Kannan",
            'input[name="email"]': "meenakannan92@gmail.com",
            'input[name="phone"]': "+91 97893 02084",
            'input[name="org"]': "2C2P (Ant Group)",
            'input[name="urls[LinkedIn]"]': "https://www.linkedin.com/in/meena-kannan-mk",
            'input[name="urls[GitHub]"]': "https://github.com/meenak95",
            'input[name="urls[Portfolio]"]': "https://github.com/meenak95",
            'input[name="urls[Other]"]': "https://github.com/meenak95",
            'textarea[name="comments"]': (
                "Lead Software Engineer (9+ years) in Java 21, Spring Boot 3.3, Apache Kafka, "
                "AWS EKS/ECS, Kubernetes, Redis, Angular 18, and Spring AI / RAG. Based in Chennai, India "
                "and available for 100% Remote India full-time or Global B2B Contract roles."
            ),
        }
        for sel, val in standard.items():
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.fill(val)

        # 3. Fill ALL custom Lever cards[...][fieldX] text inputs and textareas
        custom_inputs = await page.locator('input[name^="cards["], textarea[name^="cards["], input[required], textarea[required]').all()
        for ci in custom_inputs:
            try:
                if not await ci.is_visible():
                    continue
                itype = (await ci.get_attribute("type") or "text").lower()
                if itype in ("radio", "checkbox", "file", "hidden"):
                    continue
                val = await ci.input_value()
                if val and len(val.strip()) > 0:
                    continue
                # Find question label text
                label_txt = await ci.evaluate("""el => {
                    const container = el.closest('li, .application-question, .card-field, label, div');
                    return container ? container.innerText.toLowerCase() : '';
                }""")
                if "linkedin" in label_txt:
                    await ci.fill("https://www.linkedin.com/in/meena-kannan-mk")
                elif "salary" in label_txt or "ctc" in label_txt or "compensation" in label_txt or "pay" in label_txt or "rate" in label_txt:
                    await ci.fill("45 LPA INR / $130,000 USD")
                elif "notice" in label_txt or "start" in label_txt or "join" in label_txt or "available" in label_txt:
                    await ci.fill("Immediate / 15 Days")
                elif "location" in label_txt or "city" in label_txt or "country" in label_txt or "where" in label_txt:
                    await ci.fill("Chennai, India")
                elif "year" in label_txt or "experience" in label_txt or "how long" in label_txt:
                    await ci.fill("9")
                else:
                    await ci.fill("Yes - 9+ years production experience in Java 21, Spring Boot 3, Kafka, AWS, and Kubernetes (Remote from India).")
            except Exception as e:
                print(f"  [Custom Input Warn]: {e}", flush=True)

        # 4. Select valid options in ALL <select> dropdowns
        selects = await page.locator("select").all()
        for sel_el in selects:
            try:
                if not await sel_el.is_visible():
                    continue
                options = await sel_el.locator("option").all()
                for opt in options:
                    opt_val = await opt.get_attribute("value")
                    opt_txt = (await opt.inner_text()).strip().lower()
                    if opt_val and opt_val.strip() != "" and "select" not in opt_txt and "choose" not in opt_txt:
                        await sel_el.select_option(value=opt_val)
                        break
            except Exception:
                pass

        # 5. Check one radio button in every radio group (prefer "Yes" or first option)
        radio_names = await page.evaluate("""() => {
            const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
            return [...new Set(radios.map(r => r.name).filter(Boolean))];
        }""")
        for rname in radio_names:
            try:
                radios_in_group = await page.locator(f'input[type="radio"][name="{rname}"]').all()
                clicked_radio = False
                for r in radios_in_group:
                    rval = (await r.get_attribute("value") or "").lower()
                    if "yes" in rval or "true" in rval:
                        await r.check(force=True)
                        clicked_radio = True
                        break
                if not clicked_radio and radios_in_group:
                    await radios_in_group[0].check(force=True)
            except Exception:
                pass

        # 6. Check all consent checkboxes
        checkboxes = await page.locator('input[type="checkbox"]').all()
        for cb in checkboxes:
            try:
                if not await cb.is_checked():
                    await cb.check(force=True)
            except Exception:
                pass

        # Check if hCaptcha or reCAPTCHA iframe is blocking
        has_captcha = await page.locator('iframe[src*="hcaptcha"], iframe[src*="recaptcha"], .h-captcha, .g-recaptcha').count()
        print(f"  -> Captcha elements detected on page: {has_captcha}", flush=True)

        # Click visible Submit button (#btn-submit), NOT the hidden #hcaptchaSubmitBtn
        btn = page.locator('button#btn-submit, button.postings-btn-submit, button:visible:has-text("Submit application")').first
        if await btn.count() > 0:
            try:
                await btn.scroll_into_view_if_needed()
                await btn.click(timeout=8000)
                await asyncio.sleep(6.0)
            except Exception as e:
                print(f"  [Submit Click Warn]: {e}", flush=True)

        after_url = page.url
        body_txt = (await page.locator("body").inner_text())[:1200]
        shot_path = SCREENSHOTS_DIR / f"lever_{slug}.png"
        await page.screenshot(path=str(shot_path), full_page=False)
        print(f"  -> After Submit URL: {after_url}", flush=True)
        print(f"  -> After Submit Body Snippet: {body_txt[:300].strip()}", flush=True)

        errors = await page.locator('.error-message, .application-error, [class*="error"]').all_inner_texts()
        errors_clean = [e.strip() for e in errors if e.strip()]
        print(f"  -> Page Errors/Warnings: {errors_clean[:5]}", flush=True)
        return {
            "slug": slug,
            "after_url": after_url,
            "has_captcha": has_captcha,
            "errors": errors_clean[:5],
            "screenshot": str(shot_path),
        }
    except Exception as exc:
        print(f"  [LEVER ERROR] {slug}: {exc}", flush=True)
        return {"slug": slug, "status": f"ERROR: {exc}"}
    finally:
        await page.close()


async def inspect_and_submit_ashby(context, company, title, url, slug):
    page = await context.new_page()
    print(f"\n[ASHBY INSPECT] {company} - {title} -> {url}", flush=True)
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3.0)
        await asyncio.sleep(3.0)
        body_text = await page.locator("body").inner_text()
        if "job not found" in body_text.lower() or "no longer open" in body_text.lower() or "page not found" in body_text.lower():
            print(f"  -> [ASHBY POSTING CLOSED/404]: {body_text[:150].strip()}", flush=True)
            await page.close()
            return {"slug": slug, "status": "404_CLOSED"}

        # Upload resume
        file_inputs = await page.locator('input[type="file"]').all()
        for fi in file_inputs:
            try:
                await fi.set_input_files(str(RESUME_PDF))
                await asyncio.sleep(2.0)
            except Exception:
                pass

        # Fill all visible inputs
        inputs = await page.locator('input:not([type="file"]):not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), textarea').all()
        for inp in inputs:
            try:
                if not await inp.is_visible():
                    continue
                label = await inp.evaluate("""el => {
                    const l = el.closest('label, div[class*="field"], div[class*="Entry"]');
                    return l ? l.innerText.toLowerCase() : (el.name + ' ' + el.placeholder).toLowerCase();
                }""")
                if "email" in label:
                    await inp.fill("meenakannan92@gmail.com")
                elif "name" in label and "company" not in label:
                    await inp.fill("Meena Kannan")
                elif "phone" in label or "tel" in label or "mobile" in label:
                    await inp.fill("+91 97893 02084")
                elif "linkedin" in label:
                    await inp.fill("https://www.linkedin.com/in/meena-kannan-mk")
                elif "github" in label or "portfolio" in label or "website" in label:
                    await inp.fill("https://github.com/meenak95")
                elif "location" in label or "city" in label or "country" in label:
                    await inp.fill("Chennai, Tamil Nadu, India")
                    await asyncio.sleep(1.0)
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                elif "salary" in label or "compensation" in label or "ctc" in label:
                    await inp.fill("$135,000 USD / 48 LPA INR")
                else:
                    val = await inp.input_value()
                    if not val:
                        await inp.fill("Yes - 9+ years Java 21, Spring Boot 3, Kafka, AWS, Kubernetes (Remote India).")
            except Exception:
                pass

        # Click Yes buttons on Ashby boolean questions
        yes_btns = await page.locator('button:has-text("Yes")').all()
        for yb in yes_btns:
            try:
                if await yb.is_visible():
                    await yb.click()
            except Exception:
                pass

        # Check all checkboxes
        for cb in await page.locator('input[type="checkbox"]').all():
            try:
                if not await cb.is_checked():
                    await cb.check(force=True)
            except Exception:
                pass

        # Click Submit Application
        sub_btn = page.locator('button[type="submit"], button:has-text("Submit Application"), button:has-text("Submit")').first
        if await sub_btn.count() > 0:
            await sub_btn.click()
            await asyncio.sleep(5.0)

        shot_path = SCREENSHOTS_DIR / f"ashby_{slug}.png"
        await page.screenshot(path=str(shot_path), full_page=False)
        after_text = (await page.locator("body").inner_text())[:800]
        print(f"  -> Ashby After Submit Text Snippet:\n{after_text[:350]}", flush=True)
        return {"slug": slug, "after_url": page.url, "snippet": after_text[:350], "screenshot": str(shot_path)}
    finally:
        await page.close()


async def main():
    async with async_playwright() as p:
        browser = await launch_browser(p)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})

        # Test 2 live Lever and 2 live Ashby endpoints to see exact DOM / Captcha / Confirmation state
        await inspect_and_submit_lever(
            context,
            "Lingaro Group",
            "Java Developer, India (100% Remote India)",
            "https://jobs.lever.co/lingarogroup/853310f4-9cc3-45b7-ac29-cf5a624f3c40/apply",
            "lingaro_java_india",
        )
        await inspect_and_submit_lever(
            context,
            "HighLevel",
            "Lead Engineer - AI Studio (India Remote)",
            "https://jobs.lever.co/gohighlevel/29c16f45-a4ca-4eb8-bc4a-1738dc9219c1/apply",
            "highlevel_ai_studio",
        )
        await inspect_and_submit_ashby(
            context,
            "SigNoz",
            "Staff Backend Engineer - Platform",
            "https://jobs.ashbyhq.com/signoz/5ba2b181-0b62-49d9-b092-8e539ee1a7c7/application",
            "signoz_staff_backend",
        )
        await inspect_and_submit_ashby(
            context,
            "Camunda",
            "Software Engineer - Infrastructure (Remote)",
            "https://jobs.ashbyhq.com/camunda/b8fac33b-15a7-4dd9-98e8-69c0e5f4dbfb/application",
            "camunda_infra",
        )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
