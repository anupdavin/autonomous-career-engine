import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

from config import BASE_DIR


RESUME_PDF_ARCHITECT = (
    BASE_DIR
    / "resumes_vault"
    / "2026-09-27_B2B_Cloud_Fintech_v1.1_b2b_java_ka"
    / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"
)
RESUME_PDF_LEAD = (
    BASE_DIR
    / "resumes_vault"
    / "2026-09-27_Mastercard_v2.1_li_rem_in_m"
    / "Meena_Kannan_Lead_Software_Engineer.pdf"
)


async def autofill_greenhouse_application(page, url: str, pdf_path: Path) -> str:
    print(f"[LiveSubm] Opening {url} ...")
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3.0)

    selectors_map = [
        (["#first_name", "input[name*='first_name']", "input[autocomplete='given-name']"], "Meena"),
        (["#last_name", "input[name*='last_name']", "input[autocomplete='family-name']"], "Kannan"),
        (["#email", "input[name*='email']", "input[type='email']"], "meenakannan92@gmail.com"),
        (["#phone", "input[name*='phone']", "input[type='tel']"], "+91 97893 02084"),
        (["input[name*='linkedin' i]", "input[aria-label*='LinkedIn' i]"], "https://www.linkedin.com/in/meena-kannan-mk"),
        (["input[name*='github' i]", "input[aria-label*='GitHub' i]", "input[aria-label*='Website' i]"], "https://github.com/meenak95"),
    ]

    filled_fields = []
    for sel_list, val in selectors_map:
        for sel in sel_list:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                try:
                    await loc.fill(val)
                    filled_fields.append(sel)
                    break
                except Exception:
                    pass

    file_inputs = page.locator("input[type='file']")
    if await file_inputs.count() > 0 and pdf_path.exists():
        try:
            await file_inputs.first.set_input_files(str(pdf_path))
            filled_fields.append(f"Uploaded PDF: {pdf_path.name}")
        except Exception:
            pass

    return f"Pre-filled {len(filled_fields)} fields ({', '.join(filled_fields)}) on {url}"


async def main() -> None:
    p = await async_playwright().start()
    browser = await p.chromium.launch(channel="msedge", headless=False)
    context = await browser.new_context(viewport={"width": 1280, "height": 900})

    targets = [
        ("https://job-boards.greenhouse.io/embed/job_app?for=elastic&token=7447426", RESUME_PDF_ARCHITECT),
        ("https://job-boards.greenhouse.io/embed/job_app?for=elastic&token=7447236", RESUME_PDF_ARCHITECT),
        ("https://job-boards.greenhouse.io/embed/job_app?for=elastic&token=7447246", RESUME_PDF_ARCHITECT),
        ("https://in.linkedin.com/jobs/view/lead-software-engineer-java-backend-at-mastercard-4388496574", RESUME_PDF_LEAD),
    ]

    for url, pdf in targets:
        page = await context.new_page()
        try:
            status = await autofill_greenhouse_application(page, url, pdf)
            print(f"  -> {status}", flush=True)
        except Exception as exc:
            print(f"  -> Opened {url} ({exc})", flush=True)

    print("\n[Live Browser Ready] Keeping Edge window open so you can click Submit...", flush=True)
    await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
