import asyncio
from playwright.async_api import async_playwright
import os

BASE_DIR = r"c:\Users\MeenaDavin\Desktop\Project 1"
SALARY = "Current: 4,800,000 INR. Expected: 5,500,000 INR"
NOTICE = "60 days"

async def auto_apply():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        
        print("Starting Everbridge...")
        try:
            page = await context.new_page()
            # Removed wait_until="networkidle" to avoid timeout
            await page.goto("https://jobs.lever.co/everbridge/ff6eacff-741a-4f60-aff4-a45e89b003a9/apply", timeout=60000)
            
            await page.wait_for_selector("input[name='name']")
            
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
            await page.screenshot(path="everbridge_submit_retry.png")
            print("Everbridge Done.")
        except Exception as e:
            print(f"Everbridge failed: {e}")
            if 'page' in locals():
                await page.screenshot(path="everbridge_error_retry.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(auto_apply())
