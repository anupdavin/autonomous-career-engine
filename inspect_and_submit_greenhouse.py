import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

from config import BASE_DIR

RESUME_PDF = (
    BASE_DIR
    / "resumes_vault"
    / "2026-09-27_B2B_Cloud_Fintech_v1.1_b2b_java_ka"
    / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"
)


async def run_auto_submit() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 1400})
        url = "https://job-boards.greenhouse.io/embed/job_app?for=elastic&token=7447426"
        print(f"Loading {url} ...")
        await page.goto(url, wait_until="networkidle", timeout=35000)
        await asyncio.sleep(2.0)

        # Inspect all inputs, selects, comboboxes, and buttons
        inputs = await page.evaluate(
            """() => {
                const els = Array.from(document.querySelectorAll('input, select, textarea, button[type="submit"], [role="combobox"]'));
                return els.map(e => ({
                    tag: e.tagName,
                    id: e.id,
                    name: e.name || '',
                    type: e.type || '',
                    label: (e.labels && e.labels[0] ? e.labels[0].innerText : '') || e.getAttribute('aria-label') || e.placeholder || '',
                    required: e.required || e.getAttribute('aria-required') === 'true'
                }));
            }"""
        )
        print("Form Elements Found:")
        for item in inputs:
            print(f"  {item}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_auto_submit())
