import asyncio
from playwright.async_api import async_playwright
import os

BASE_DIR = r"c:\Users\MeenaDavin\Desktop\Project 1"
SALARY = "Current: 110k SGD. Expected: 3 to 4 lakhs and above"
NOTICE = "60 days"

async def auto_apply():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        
        # --- OPORTUN (Greenhouse) ---
        print("Starting Oportun...")
        try:
            page = await context.new_page()
            await page.goto("https://job-boards.greenhouse.io/oportun/jobs/4699315005", wait_until="networkidle")
            
            # Click apply to scroll down
            apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply')").first
            if await apply_btn.count() > 0:
                await apply_btn.click()
            
            # Use broad selectors
            await page.locator("input[name*='first_name'], #first_name").first.fill("Meena")
            await page.locator("input[name*='last_name'], #last_name").first.fill("Kannan")
            await page.locator("input[name*='email'], #email").first.fill("meenakannan92@gmail.com")
            await page.locator("input[name*='phone'], #phone").first.fill("+919789302084")
            
            pdf1 = os.path.join(BASE_DIR, "application_drafts", "2026-09-28_meena_kannan_oportun_r14037_resume.pdf")
            if os.path.exists(pdf1):
                await page.locator("input[type='file']").first.set_input_files(pdf1)
            
            # Custom fields
            custom_fields = await page.locator("div.field").all()
            for field in custom_fields:
                text = (await field.inner_text()).lower()
                input_loc = field.locator("input[type='text'], select")
                if await input_loc.count() > 0:
                    if "city" in text:
                        await input_loc.first.fill("Chennai")
                    elif "state" in text:
                        await input_loc.first.fill("Tamil Nadu")
                    elif "country" in text:
                        tag = await input_loc.first.evaluate("el => el.tagName")
                        if tag == "SELECT":
                            opts = await input_loc.first.locator("option").all_inner_texts()
                            for o in opts:
                                if "India" in o:
                                    await input_loc.first.select_option(label=o)
                                    break
                        else:
                            await input_loc.first.fill("India")
            
            await page.locator("#submit_app, button:has-text('Submit Application')").first.click()
            await page.wait_for_timeout(6000)
            await page.screenshot(path="oportun_submit.png")
            print("Oportun Done.")
        except Exception as e:
            print(f"Oportun failed: {e}")
            if 'page' in locals():
                await page.screenshot(path="oportun_error.png")
            
        # --- ELTROPY (Greenhouse) ---
        print("Starting Eltropy...")
        try:
            page = await context.new_page()
            await page.goto("https://job-boards.greenhouse.io/eltropyinc/jobs/4074779009", wait_until="networkidle")
            
            apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply')").first
            if await apply_btn.count() > 0:
                await apply_btn.click()
                
            await page.locator("input[name*='first_name'], #first_name").first.fill("Meena")
            await page.locator("input[name*='last_name'], #last_name").first.fill("Kannan")
            await page.locator("input[name*='email'], #email").first.fill("meenakannan92@gmail.com")
            await page.locator("input[name*='phone'], #phone").first.fill("+919789302084")
            
            pdf2 = os.path.join(BASE_DIR, "application_drafts", "2026-09-28_meena_kannan_eltropy_resume.pdf")
            if os.path.exists(pdf2):
                await page.locator("input[type='file']").first.set_input_files(pdf2)
            
            custom_fields = await page.locator("div.field").all()
            for field in custom_fields:
                text = (await field.inner_text()).lower()
                input_loc = field.locator("input[type='text'], select")
                if await input_loc.count() > 0:
                    if "location (city)" in text or "city" in text:
                        await input_loc.first.fill("Chennai")
            
            await page.locator("#submit_app, button:has-text('Submit Application')").first.click()
            await page.wait_for_timeout(6000)
            await page.screenshot(path="eltropy_submit.png")
            print("Eltropy Done.")
        except Exception as e:
            print(f"Eltropy failed: {e}")
            if 'page' in locals():
                await page.screenshot(path="eltropy_error.png")

        # --- EVERBRIDGE (Lever) ---
        print("Starting Everbridge...")
        try:
            page = await context.new_page()
            # Append /apply for Lever!
            await page.goto("https://jobs.lever.co/everbridge/ff6eacff-741a-4f60-aff4-a45e89b003a9/apply", wait_until="networkidle")
            
            await page.locator("input[name='name']").first.fill("Meena Kannan")
            await page.locator("input[name='email']").first.fill("meenakannan92@gmail.com")
            await page.locator("input[name='phone']").first.fill("+919789302084")
            await page.locator("input[name='org']").first.fill("NCS")
            
            pdf3 = os.path.join(BASE_DIR, "application_drafts", "2026-09-28_meena_kannan_everbridge_backend_ai_resume.pdf")
            if os.path.exists(pdf3):
                await page.locator("input[type='file']").first.set_input_files(pdf3)
            
            custom_fields = await page.locator("li.application-question, div.application-question, .custom-question").all()
            for field in custom_fields:
                try:
                    text = (await field.inner_text()).lower()
                    input_loc = field.locator("input[type='text'], textarea, select")
                    if await input_loc.count() > 0:
                        target = input_loc.first
                        tag = await target.evaluate("el => el.tagName")
                        
                        val = ""
                        if "salary" in text or "compensation" in text:
                            val = SALARY
                        elif "notice" in text:
                            val = NOTICE
                        elif "location" in text or "city" in text:
                            val = "Chennai, Tamil Nadu"
                        elif "ai" in text or "tools" in text:
                            val = "Claude Code, GitHub Copilot, Antigravity, Codex"
                        elif "prior employment" in text or "relatives" in text or "family" in text:
                            val = "No"
                            if tag == "SELECT":
                                opts = await target.locator("option").all_inner_texts()
                                for o in opts:
                                    if "no" in o.lower():
                                        await target.select_option(label=o)
                                        val = ""
                                        break
                        
                        if val:
                            if tag == "SELECT":
                                try:
                                    await target.select_option(label=val)
                                except:
                                    await target.select_option(value=val)
                            else:
                                await target.fill(val)
                except:
                    pass
            
            await page.locator("button.postings-btn[data-qa='btn-submit']").first.click()
            await page.wait_for_timeout(6000)
            await page.screenshot(path="everbridge_submit.png")
            print("Everbridge Done.")
        except Exception as e:
            print(f"Everbridge failed: {e}")
            if 'page' in locals():
                await page.screenshot(path="everbridge_error.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(auto_apply())
