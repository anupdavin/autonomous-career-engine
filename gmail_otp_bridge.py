import email
import imaplib
import os
import re
from pathlib import Path
from typing import Optional

from config import BASE_DIR

OTP_FILE = BASE_DIR / "greenhouse_otp_code.txt"
ENV_FILE = BASE_DIR / ".env"

# LAYER 1: Dedicated Sub-Address Tag used ONLY on job portals (Banks/Google/Personal never send to +jobs)
REQUIRED_RECIPIENT_SUBADDRESS = "meenakannan92+jobs@gmail.com"

# LAYER 2: Strict ATS Sender Domain Allowlist (Only job boards allowed)
ALLOWED_ATS_SENDERS = (
    "us.greenhouse-mail.io",
    "greenhouse.io",
    "ashbyhq.com",
    "lever.co",
    "myworkday.com",
    "workablemail.com",
    "smartrecruiters.com",
)

# LAYER 3: Hard Blocklist of Sensitive / Financial / Account-Security Terms
SENSITIVE_BLOCKLIST_TERMS = (
    "bank",
    "transaction",
    "debit",
    "credit card",
    "netbanking",
    "upi",
    "aadhaar",
    "pan card",
    "income tax",
    "password reset",
    "reset your password",
    "google account",
    "2-step verification",
    "sign-in attempt",
    "login otp",
    "do not share this otp",
)

# Exact Gmail Filter String you can paste into Gmail Settings -> Filters -> Create a new filter:
GMAIL_STRICT_FILTER_QUERY = (
    'to:(meenakannan92+jobs@gmail.com) '
    'from:(us.greenhouse-mail.io OR greenhouse.io OR ashbyhq.com OR myworkday.com OR lever.co) '
    '("security code field on your application" OR "submit your application") '
    '-"password reset" -"2-step" -"bank" -"transaction"'
)


def extract_strictly_ats_application_code(sender: str, recipient: str, subject: str, body: str) -> Optional[str]:
    """
    4-Layer Security Gate:
      1. Sender MUST end with a known ATS domain in ALLOWED_ATS_SENDERS.
      2. Subject and Body MUST NOT contain any term in SENSITIVE_BLOCKLIST_TERMS.
      3. Body MUST contain the exact ATS job application context phrase ("security code field on your application"
         or "submit your application").
      4. Extracts ONLY the 8-character code and discards the entire email text.
    """
    sender_low = sender.lower()
    if not any(domain in sender_low for domain in ALLOWED_ATS_SENDERS):
        return None

    combined_low = f"{subject} {body}".lower()
    if any(blocked in combined_low for blocked in SENSITIVE_BLOCKLIST_TERMS):
        return None

    # LAYER 4: Context-Anchored Regex (Requires the exact Greenhouse/ATS application sentence before the code)
    anchored_match = re.search(
        r"(?:security code field on your application|enter the 8-character code|verification code for your application)[^A-Za-z0-9]{1,40}([A-Za-z0-9]{8})\b",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    if anchored_match:
        return anchored_match.group(1).strip()
    return None
