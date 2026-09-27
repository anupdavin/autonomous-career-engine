import asyncio
import random
from pathlib import Path
from playwright.async_api import async_playwright

from config import BASE_DIR
from gmail_otp_bridge import fetch_latest_ats_otp

RESUME_PDF = (
    BASE_DIR
    / "resumes_vault"
    / "2026-09-27_B2B_Cloud_Fintech_v1.1_b2b_java_ka"
    / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"
)
APPFIRE_COVER = BASE_DIR / "appfire_cover_note.txt"
SCREENSHOT_APPFIRE = BASE_DIR / "appfire_submit_state.png"
OTP_FILE = BASE_DIR / "greenhouse_otp_code.txt"


async def human_move_and_click(page, locator):
    if await locator.count() == 0:
        return
    await locator.scroll_into_view_if_needed()
    box = await locator.bounding_box()
    if box:
        tx = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        ty = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        await page.mouse.move(tx, ty, steps=random.randint(8, 16))
        await asyncio.sleep(random.uniform(0.12, 0.25))
    await locator.click()


async def select_react_guaranteed(page, input_id: str, preferred_queries: list[str]) -> str:
    loc = page.locator(f"[id='{input_id}']").first
    if await loc.count() == 0:
        return "missing"

    for q in preferred_queries + [""]:
        await human_move_and_click(page, loc)
        await asyncio.sleep(0.3)
        await loc.fill("")
        if q:
            await loc.press_sequentially(q, delay=45)
        else:
            await page.keyboard.press("ArrowDown")

        for _ in range(5):
            await asyncio.sleep(0.4)
            opts = page.locator(".select__option:visible")
            cnt = await opts.count()
            if cnt > 0:
                for i in range(cnt):
                    t = (await opts.nth(i).inner_text()).strip()
                    low = t.lower()
                    if "loading" in low or "type to" in low or "no options" in low:
                        continue
                    if "British" not in t and "Indiana" not in t:
                        await opts.nth(i).click()
                        await asyncio.sleep(0.35)
                        return f"Selected: {t}"
    return "no_option"


async def try_enter_code(page, candidate_code: str) -> bool:
    for idx, ch in enumerate(candidate_code[:8]):
        box = page.locator(f"#security-input-{idx}")
        if await box.count() > 0:
            await box.fill("")
            await box.fill(ch)
    await asyncio.sleep(0.6)
    await page.locator("button[type='submit']").first.click()
    await asyncio.sleep(5.5)
    await page.screenshot(path=str(SCREENSHOT_APPFIRE), full_page=True)
    body = " ".join((await page.locator("body").inner_text()).split())
    if "invalid security code" in body.lower():
        print(f"  [Appfire Code '{candidate_code}' -> Invalid security code]", flush=True)
        return False
    print(f"  [APPFIRE SUCCESS with '{candidate_code}'!]: {body[:350]}", flush=True)
    return True


async def main() -> None:
    if OTP_FILE.exists():
        OTP_FILE.unlink()
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        channel="msedge",
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--disable-infobars", "--no-sandbox"],
    )
    context = await browser.new_context(
        viewport={"width": 1366, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    )
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); window.chrome = { runtime: {} };"
    )

    page = await context.new_page()
    url = "https://job-boards.greenhouse.io/appfire/jobs/4706397005"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(2.5)

    await page.locator("#first_name").fill("Meena")
    await page.locator("#last_name").fill("Kannan")
    if await page.locator("#preferred_name").count() > 0:
        await page.locator("#preferred_name").fill("Meena")
    await page.locator("#email").fill("meenakannan92@gmail.com")
    await select_react_guaranteed(page, "country", ["India"])
    await page.locator("#phone").fill("9789302084")

    if RESUME_PDF.exists():
        await page.locator("#resume").set_input_files(str(RESUME_PDF))
    if APPFIRE_COVER.exists() and await page.locator("#cover_letter").count() > 0:
        await page.locator("#cover_letter").set_input_files(str(APPFIRE_COVER))
    await asyncio.sleep(1.0)

    combos = page.locator("input[id*='question_'][aria-autocomplete='list'], input[id*='location'][aria-autocomplete='list']")
    for i in range(await combos.count()):
        inp = combos.nth(i)
        inp_id = await inp.get_attribute("id")
        lbl_el = page.locator(f"label[for='{inp_id}']")
        lbl = (await lbl_el.inner_text()).strip().lower() if await lbl_el.count() > 0 else inp_id.lower()
        if "sponsorship" in lbl or "visa" in lbl:
            await select_react_guaranteed(page, inp_id, ["No", "Yes"])
        elif "eligible" in lbl or "work" in lbl or "acknowledge" in lbl or "privacy" in lbl or "terms" in lbl:
            await select_react_guaranteed(page, inp_id, ["Yes", "I acknowledge", "Poland"])
        elif "location" in lbl or "city" in lbl:
            await select_react_guaranteed(page, inp_id, ["Poland"])
        else:
            await select_react_guaranteed(page, inp_id, ["Yes", ""])

    t_inputs = page.locator("input.input[type='text'][id^='question_'], textarea[id^='question_']")
    for i in range(await t_inputs.count()):
        inp = t_inputs.nth(i)
        inp_id = await inp.get_attribute("id")
        lbl_el = page.locator(f"label[for='{inp_id}']")
        low = (await lbl_el.inner_text()).strip().lower() if await lbl_el.count() > 0 else ""
        if "linkedin" in low:
            await inp.fill("https://www.linkedin.com/in/meena-kannan-mk")
        elif "website" in low or "github" in low or "portfolio" in low:
            await inp.fill("https://github.com/meenak95")
        elif "salary" in low or "compensation" in low or "expectation" in low:
            await inp.fill("85000 USD / yr (Global B2B or India Entity)")
        elif "notice" in low or "start" in low or "available" in low:
            await inp.fill("Immediate / 15 Days")
        else:
            await inp.fill("India - Immediate Availability (Global B2B or India Entity)")

    cbs = page.locator("input[type='checkbox']")
    for i in range(await cbs.count()):
        cb = cbs.nth(i)
        if not await cb.is_checked():
            try:
                await cb.check()
            except Exception:
                pass

    await asyncio.sleep(1.0)
    await page.locator("button[type='submit']").first.click()
    await asyncio.sleep(6.0)
    await page.screenshot(path=str(SCREENSHOT_APPFIRE), full_page=True)
    print("[APPFIRE READY FOR 8-CHAR CODE] Sent fresh verification code to meenakannan92@gmail.com", flush=True)

    for _ in range(720):
        raw = fetch_latest_ats_otp()
        if not raw and OTP_FILE.exists():
            raw = OTP_FILE.read_text(encoding="utf-8").strip().replace(" ", "")
            OTP_FILE.unlink()
        if raw and len(raw) >= 6:
            variants = [raw]
            if "l" in raw:
                variants.append(raw.replace("l", "I"))
            if "I" in raw:
                variants.append(raw.replace("I", "l"))
            for v in variants:
                ok = await try_enter_code(page, v)
                if ok:
                    await browser.close()
                    await p.stop()
                    return
        await asyncio.sleep(3.0)


if __name__ == "__main__":
    asyncio.run(main())
