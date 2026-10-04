import asyncio
from playwright.async_api import async_playwright
import os

BASE_DIR = r"c:\Users\MeenaDavin\Desktop\Project 1"
NOTICE = "60 days"

async def auto_apply():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        
        # --- LINGARO (Lever) ---
        print("Starting Lingaro...")
        try:
            page = await context.new_page()
            await page.goto("https://jobs.lever.co/lingarogroup/f3231a28-9a57-41f2-8bd0-5638bc520904/apply", wait_until="networkidle")
            
            await page.locator("input[name='name']").first.fill("Meena Kannan")
            await page.locator("input[name='email']").first.fill("meenakannan92@gmail.com")
            await page.locator("input[name='phone']").first.fill("+919789302084")
            await page.locator("input[name='org']").first.fill("NCS")
            
            pdf = os.path.join(BASE_DIR, "application_drafts", "2026-09-28_meena_kannan_eltropy_resume.pdf")
            if os.path.exists(pdf):
                await page.locator("input[type='file']").first.set_input_files(pdf)
            
            custom_fields = await page.locator("li.application-question, div.application-question, .custom-question").all()
            for field in custom_fields:
                try:
                    text = (await field.inner_text()).lower()
                    input_loc = field.locator("input[type='text'], textarea, select")
                    if await input_loc.count() > 0:
                        target = input_loc.first
                        tag = await target.evaluate("el => el.tagName")
                        
                        val = ""
                        if "notice" in text:
                            val = NOTICE
                        elif "location" in text or "city" in text:
                            val = "Chennai, Tamil Nadu"
                        
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
            
            await page.locator("button:has-text('Submit application')").first.click()
            await page.wait_for_timeout(6000)
            await page.screenshot(path="lingaro_submit.png")
            print("Lingaro Done.")
        except Exception as e:
            print(f"Lingaro failed: {e}")
            if 'page' in locals():
                await page.screenshot(path="lingaro_error.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(auto_apply())

