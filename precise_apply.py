import asyncio
from playwright.async_api import async_playwright
import json
from pathlib import Path

# Job URLs
OPORTUN_URL = "https://job-boards.greenhouse.io/oportun/jobs/4699315005"
ELTROPY_URL = "https://job-boards.greenhouse.io/eltropyinc/jobs/4074779009"
EVERBRIDGE_URL = "https://jobs.lever.co/everbridge/ff6eacff-741a-4f60-aff4-a45e89b003a9/apply"

# Paths
WORKSPACE = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
RESUME_DIR = WORKSPACE / "application_drafts"
OPORTUN_RESUME = RESUME_DIR / "2026-09-28_meena_kannan_oportun_r14037_resume.pdf"
ELTROPY_RESUME = RESUME_DIR / "2026-09-28_meena_kannan_eltropy_resume.pdf"
EVERBRIDGE_RESUME = RESUME_DIR / "2026-09-28_meena_kannan_everbridge_backend_ai_resume.pdf"

OPORTUN_COVER = (RESUME_DIR / "2026-09-28_oportun_r14037_cover_note.txt").read_text(encoding="utf-8")
ELTROPY_COVER = (RESUME_DIR / "2026-09-28_eltropy_senior_backend_cover_note.txt").read_text(encoding="utf-8")
EVERBRIDGE_COVER = (RESUME_DIR / "2026-09-28_everbridge_backend_ai_cover_note.txt").read_text(encoding="utf-8")

async def apply_oportun(page):
    print("Applying to Oportun...")
    await page.goto(OPORTUN_URL, timeout=30000)
    await page.wait_for_selector('input[id="first_name"]')
    
    # Basic info
    await page.fill('input[id="first_name"]', "Meena")
    await page.fill('input[id="last_name"]', "Kannan")
    await page.fill('input[id="email"]', "meenakannan92@gmail.com")
    await page.fill('input[id="phone"]', "9789302084")
    
    # Location (Autocomplete)
    loc_input = page.locator('input[id="job_application_answers_attributes_0_text_value"]')
    if await loc_input.count() > 0:
        await loc_input.fill("Chennai, Tamil Nadu, India")
    else:
        # Fallback if id differs
        await page.fill('input[autocomplete="custom-address"]', "Chennai, Tamil Nadu, India")
    
    # Wait for the autocomplete dropdown and click the first option if it appears
    try:
        await page.wait_for_selector('li.ui-menu-item', timeout=2000)
        await page.click('li.ui-menu-item')
    except Exception:
        pass
        
    await page.fill('input[id="job_application_answers_attributes_1_text_value"]', "Chennai")
    await page.fill('input[id="job_application_answers_attributes_2_text_value"]', "Tamil Nadu")
    
    # Country dropdown
    await page.select_option('select[id="job_application_answers_attributes_3_text_value"]', label="India")
    
    # Resume
    await page.set_input_files('input[name="job_application[answers_attributes][4][attachment_attributes][file]"]', str(OPORTUN_RESUME))
    # Wait for resume upload
    await asyncio.sleep(2)
    
    # Ensure all required checkboxes are filled if any
    
    # Submit
    await page.click('input[id="submit_app"]')
    
    # Wait for confirmation
    await page.wait_for_selector('text="Application Submitted"', timeout=10000)
    print("Oportun Application Submitted.")

async def apply_eltropy(page):
    print("Applying to Eltropy...")
    await page.goto(ELTROPY_URL, timeout=30000)
    await page.wait_for_selector('input[id="first_name"]')
    
    await page.fill('input[id="first_name"]', "Meena")
    await page.fill('input[id="last_name"]', "Kannan")
    await page.fill('input[id="email"]', "meenakannan92@gmail.com")
    await page.fill('input[id="phone"]', "9789302084")
    
    # Location autocomplete
    loc_input = page.locator('input[autocomplete="custom-address"]')
    await loc_input.fill("Chennai, Tamil Nadu, India")
    try:
        await page.wait_for_selector('li.ui-menu-item', timeout=2000)
        await page.click('li.ui-menu-item')
    except Exception:
        pass
    
    # LinkedIn
    try:
        await page.fill('input:has-text("LinkedIn")', "https://www.linkedin.com/in/meena-kannan-mk")
    except:
        pass
    
    # Resume
    await page.locator('button[data-source="attach"]').first.click()
    await page.set_input_files('input[type="file"]', str(ELTROPY_RESUME))
    await asyncio.sleep(2)
    
    # Cover Letter
    try:
        await page.locator('button[data-source="paste"]').nth(1).click()
        await page.fill('textarea', ELTROPY_COVER)
    except:
        pass
        
    await page.click('input[id="submit_app"]')
    await page.wait_for_selector('text="Application Submitted"', timeout=10000)
    print("Eltropy Application Submitted.")

async def apply_everbridge(page):
    print("Applying to Everbridge...")
    await page.goto(EVERBRIDGE_URL, timeout=30000)
    await page.wait_for_selector('input[name="name"]')
    
    await page.fill('input[name="name"]', "Meena Kannan")
    await page.fill('input[name="email"]', "meenakannan92@gmail.com")
    await page.fill('input[name="phone"]', "+91 97893 02084")
    await page.fill('input[name="org"]', "2C2P")
    
    # Resume
    await page.set_input_files('input[type="file"]', str(EVERBRIDGE_RESUME))
    await asyncio.sleep(2)
    
    # URLs
    try:
        await page.fill('input[name="urls[LinkedIn]"]', "https://www.linkedin.com/in/meena-kannan-mk")
        await page.fill('input[name="urls[GitHub]"]', "https://github.com/meenak95")
    except:
        pass
    
    # Comments (Cover Letter)
    await page.fill('textarea[name="comments"]', EVERBRIDGE_COVER)
    
    # Custom Questions
    inputs = await page.locator('input[type="text"]').all()
    for inp in inputs:
        placeholder = await inp.get_attribute("placeholder") or ""
        name = await inp.get_attribute("name") or ""
        text_content = await inp.text_content() or ""
        
        # We need to answer custom questions for Everbridge
        # They don't have placeholders, but labels near them. Lever form creates cards.
        # Let's just find the text in the DOM and fill the corresponding input.
    
    cards = await page.locator('.custom-question').all()
    for card in cards:
        label = (await card.inner_text()).lower()
        if "salary" in label:
            await card.locator('input').fill("4,800,000 INR current, Open to discussion expected")
        elif "notice" in label:
            await card.locator('input').fill("60 days")
        elif "location" in label:
            await card.locator('input').fill("Chennai, Tamil Nadu, India")
        elif "tools" in label or "ai" in label:
            await card.locator('textarea').fill("Claude, GitHub Copilot")
        elif "relative" in label or "employment" in label:
            if await card.locator('select').count() > 0:
                await card.locator('select').select_option(label="No")
            elif await card.locator('input').count() > 0:
                await card.locator('input').fill("No")

    # Consent checkbox
    consent = page.locator('input[type="checkbox"]')
    if await consent.count() > 0:
        await consent.check()

    await page.click('button:has-text("Submit application")')
    await page.wait_for_selector('text="Application submitted"', timeout=10000)
    print("Everbridge Application Submitted.")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            await apply_oportun(page)
        except Exception as e:
            print(f"Failed Oportun: {e}")
            
        try:
            await apply_eltropy(page)
        except Exception as e:
            print(f"Failed Eltropy: {e}")
            
        try:
            await apply_everbridge(page)
        except Exception as e:
            print(f"Failed Everbridge: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
