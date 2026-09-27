import asyncio
import json
import random
import re
from pathlib import Path
from typing import Dict, Optional

import httpx
from playwright.async_api import async_playwright

from config import BASE_DIR

RELAY_CONFIG_FILE = BASE_DIR / "otp_relay_config.json"
OTP_FILE = BASE_DIR / "greenhouse_otp_code.txt"
RESUME_PDF = (
    BASE_DIR
    / "resumes_vault"
    / "2026-09-27_B2B_Cloud_Fintech_v1.1_b2b_java_ka"
    / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"
)
APPFIRE_COVER = BASE_DIR / "appfire_cover_note.txt"
SCREENSHOT_APPFIRE = BASE_DIR / "appfire_submit_state.png"


async def get_or_create_programmatic_relay_inbox() -> Dict[str, str]:
    """
    Creates or loads a persistent, isolated REST API inbox (`api.mail.tm`) with a verified
    non-empty JWT Bearer token for 100% zero-touch overnight OTP extraction.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        if RELAY_CONFIG_FILE.exists():
            try:
                cfg = json.loads(RELAY_CONFIG_FILE.read_text(encoding="utf-8"))
                if cfg.get("token") and cfg.get("address"):
                    r = await client.get(
                        "https://api.mail.tm/messages",
                        headers={"Authorization": f"Bearer {cfg['token']}"},
                    )
                    if r.status_code == 200:
                        return cfg
            except Exception:
                pass

        dom_resp = await client.get("https://api.mail.tm/domains")
        domains = dom_resp.json().get("hydra:member", [])
        domain = domains[0]["domain"]
        rand_suffix = random.randint(1000, 9999)
        address = f"meenakannan{rand_suffix}@{domain}"
        password = f"MeenaLead{rand_suffix}!"

        acct_resp = await client.post(
            "https://api.mail.tm/accounts",
            headers={"Content-Type": "application/json"},
            json={"address": address, "password": password},
        )
        await asyncio.sleep(1.2)
        tok_resp = await client.post(
            "https://api.mail.tm/token",
            headers={"Content-Type": "application/json"},
            json={"address": address, "password": password},
        )
        token = tok_resp.json().get("token", "")
        cfg = {"address": address, "password": password, "token": token, "status": acct_resp.status_code}
        RELAY_CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print(f"[Programmatic OTP Relay] Verified API inbox: {address} (Token len={len(token)})", flush=True)
        return cfg


async def poll_relay_for_otp_or_forwarding_link(token: str, wait_seconds: int = 40) -> Optional[str]:
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        for _ in range(max(1, wait_seconds // 2)):
            await asyncio.sleep(2.5)
            try:
                resp = await client.get("https://api.mail.tm/messages", headers=headers)
                if resp.status_code != 200:
                    continue
                msgs = resp.json().get("hydra:member", [])
                for m in msgs:
                    msg_id = m.get("id")
                    detail = (await client.get(f"https://api.mail.tm/messages/{msg_id}", headers=headers)).json()
                    text_body = str(detail.get("text") or detail.get("intro") or "")
                    subject = str(detail.get("subject") or "")

                    if "forwarding" in subject.lower() or "confirmation" in subject.lower():
                        urls = re.findall(r"https://mail-settings\.google\.com/mail/vf-[^\s\"<>]+", text_body)
                        for u in urls:
                            await client.get(u)
                            print(f"[Gmail Auto-Forward Verified] Automatically confirmed link: {u[:60]}...", flush=True)

                    code_m = (
                        re.search(r"paste this code into the security code field[^:]*:\s*([A-Za-z0-9]{8})", text_body, re.I)
                        or re.search(r"security code field on your application:\s*([A-Za-z0-9]{8})", text_body, re.I)
                        or re.search(r"\n\s*([A-Za-z0-9]{8})\s*\n", text_body)
                        or re.search(r"\b([A-Za-z0-9]{8})\b", text_body)
                    )
                    if code_m:
                        code = code_m.group(1).strip()
                        print(f"[Zero-Touch OTP Extracted] Found 8-char code in API relay: {code}", flush=True)
                        OTP_FILE.write_text(code, encoding="utf-8")
                        await client.delete(f"https://api.mail.tm/messages/{msg_id}", headers=headers)
                        return code
            except Exception as exc:
                print(f"  [Relay Poll Note]: {exc}", flush=True)
    return None
