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
COVER_TXT = (
    BASE_DIR
    / "resumes_vault"
    / "2026-09-27_B2B_Cloud_Fintech_v1.1_b2b_java_ka"
    / "cover_note.txt"
)
SCREENSHOT_FILE = BASE_DIR / "greenhouse_submit_state.png"
STATUS_FILE = BASE_DIR / "greenhouse_live_status.txt"
OTP_FILE = BASE_DIR / "greenhouse_otp_code.txt"


async def select_react_option_visible(page, input_id: str, text_to_type: str, exact_match: str = "") -> str:
    loc = page.locator(f"[id='{input_id}']").first
    if await loc.count() == 0:
        return "missing"
    await loc.scroll_into_view_if_needed()
    await loc.click()
    await asyncio.sleep(0.4)
    if text_to_type:
        await loc.fill(text_to_type)
    else:
        await page.keyboard.press("ArrowDown")
    for _ in range(8):
        await asyncio.sleep(0.5)
        opts = page.locator(".select__option:visible")
        count = await opts.count()
        if count > 0:
            for i in range(count):
                t = (await opts.nth(i).inner_text()).strip()
                if "loading" in t.lower() or "type to" in t.lower() or "no options" in t.lower():
                    continue
                if exact_match and t == exact_match:
                    await opts.nth(i).click()
                    await asyncio.sleep(0.4)
                    return f"Selected exact: {t}"
                if "British" not in t and "Indiana" not in t:
                    await opts.nth(i).click()
                    await asyncio.sleep(0.4)
                    return f"Selected option: {t}"
    return "no_option_matched"


async def select_location_guaranteed(page, input_id: str) -> str:
    loc = page.locator(f"[id='{input_id}']").first
    if await loc.count() == 0:
        return "not_present"

    for query in ["Bangalore", "Chennai", "India"]:
        await loc.scroll_into_view_if_needed()
        await loc.click()
        await asyncio.sleep(0.4)
        await loc.fill("")
        await asyncio.sleep(0.2)
        await loc.press_sequentially(query, delay=80)

        for _ in range(8):
            await asyncio.sleep(0.5)
            opts = page.locator(".select__option:visible")
            cnt = await opts.count()
            if cnt > 0:
                texts = [(await opts.nth(i).inner_text()).strip() for i in range(cnt)]
                for i, txt in enumerate(texts):
                    low = txt.lower()
                    if "loading" not in low and "no options" not in low and "type to" not in low:
                        await opts.nth(i).click()
                        await asyncio.sleep(0.5)
                        return f"Selected: {txt}"
    return "failed_all_queries"


async def try_enter_code(page, candidate_code: str) -> bool:
    for idx, ch in enumerate(candidate_code[:8]):
        box = page.locator(f"#security-input-{idx}")
        if await box.count() > 0:
            await box.fill("")
            await box.fill(ch)
    await asyncio.sleep(0.6)
    await page.locator("button[type='submit']").first.click()
    await asyncio.sleep(5.5)
    await page.screenshot(path=str(SCREENSHOT_FILE), full_page=True)
    body = " ".join((await page.locator("body").inner_text()).split())
    STATUS_FILE.write_text(body[:600], encoding="utf-8")
    if "invalid security code" in body.lower():
        print(f"  [Code '{candidate_code}' -> Invalid security code]", flush=True)
        return False
    print(f"  [SUCCESS with '{candidate_code}'!]: {body[:300]}", flush=True)
    return True


async def main() -> None:
    if OTP_FILE.exists():
        OTP_FILE.unlink()
    p = await async_playwright().start()
    browser = await p.chromium.launch(channel="msedge", headless=True)
    context = await browser.new_context(viewport={"width": 1280, "height": 1200})
    page = await context.new_page()

    url = "https://job-boards.greenhouse.io/embed/job_app?for=elastic&token=7447426"
    await page.goto(url, wait_until="networkidle", timeout=35000)
    await asyncio.sleep(1.5)

    await page.locator("#first_name").fill("Meena")
    await page.locator("#last_name").fill("Kannan")
    if await page.locator("#preferred_name").count() > 0:
        await page.locator("#preferred_name").fill("Meena")
    await page.locator("#email").fill("meenakannan92@gmail.com")
    await select_react_option_visible(page, "country", "India", exact_match="India (+91)")
    await page.locator("#phone").fill("9789302084")

    if RESUME_PDF.exists():
        await page.locator("#resume").set_input_files(str(RESUME_PDF))
    if COVER_TXT.exists():
        await page.locator("#cover_letter").set_input_files(str(COVER_TXT))
    await asyncio.sleep(1.0)

    combos = page.locator("input[id*='question_'][aria-autocomplete='list']")
    for i in range(await combos.count()):
        inp = combos.nth(i)
        inp_id = await inp.get_attribute("id")
        lbl_el = page.locator(f"label[for='{inp_id}']")
        lbl = (await lbl_el.inner_text()).strip() if await lbl_el.count() > 0 else inp_id
        low = lbl.lower()
        if "location" in low:
            await select_location_guaranteed(page, inp_id)
        elif "certification" in low or "sponsorship" in low:
            await select_react_option_visible(page, inp_id, "No", exact_match="No")
        elif "travel" in low:
            await select_react_option_visible(page, inp_id, "Yes", exact_match="Yes")
        elif "acknowledge" in low or "privacy" in low:
            await select_react_option_visible(page, inp_id, "I acknowledge", exact_match="I acknowledge")
        else:
            await select_react_option_visible(page, inp_id, "", exact_match="")

    t_inputs = page.locator("input.input[type='text'][id^='question_']")
    for i in range(await t_inputs.count()):
        inp = t_inputs.nth(i)
        inp_id = await inp.get_attribute("id")
        lbl_el = page.locator(f"label[for='{inp_id}']")
        low = (await lbl_el.inner_text()).strip().lower() if await lbl_el.count() > 0 else ""
        if "linkedin" in low:
            await inp.fill("https://www.linkedin.com/in/meena-kannan-mk")
        elif "github" in low or "website" in low or "professional" in low:
            await inp.fill("https://github.com/meenak95")
        elif "right to work" in low or "countries" in low:
            await inp.fill("India")
        elif "pronoun" in low:
            await inp.fill("She/Her")
        else:
            await inp.fill("Yes")

    cbs = page.locator("input[type='checkbox'][id^='question_']")
    for i in range(await cbs.count()):
        cb = cbs.nth(i)
        if not await cb.is_checked():
            await cb.check()

    await asyncio.sleep(1.0)
    await page.locator("button[type='submit']").first.click()
    await asyncio.sleep(6.0)
    await page.screenshot(path=str(SCREENSHOT_FILE), full_page=True)
    print("[READY FOR LATEST 8-CHAR CODE] Sent exactly 1 fresh email to meenakannan92@gmail.com", flush=True)

    # Stay open and retry variants if l/I ambiguity occurs; NEVER close on Invalid security code!
    for _ in range(720):
        if OTP_FILE.exists():
            raw = OTP_FILE.read_text(encoding="utf-8").strip().replace(" ", "")
            OTP_FILE.unlink()
            if len(raw) >= 6:
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
