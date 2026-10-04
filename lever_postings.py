"""Pure normalization for public Lever job postings."""

from __future__ import annotations

import html
import re
from typing import Any

from eligibility import global_remote_evidence


TARGET_KEYWORDS = (
    "java",
    "spring",
    "lead",
    "staff",
    "principal",
    "architect",
    "microservices",
    "kafka",
    "kubernetes",
    "backend",
    "ai",
    "cloud",
    "rag",
    "distributed",
    "platform",
    "solutions",
    "consulting",
    "tech lead",
    "software engineer",
)


def parse_lever_posting(posting: dict[str, Any], site_slug: str, company_label: str) -> dict[str, Any] | None:
    """Normalize a public Lever posting, retaining only explicit India-remote evidence."""
    title = str(posting.get("text", "")).strip()
    posting_id = str(posting.get("id", "")).strip()
    if not title or not posting_id or not any(term in title.casefold() for term in TARGET_KEYWORDS):
        return None

    categories = posting.get("categories")
    categories = categories if isinstance(categories, dict) else {}
    primary_location = str(categories.get("location", "")).strip()
    all_locations = categories.get("allLocations", [])
    if isinstance(all_locations, list):
        location_items = [str(value).strip() for value in all_locations if str(value).strip()]
    elif isinstance(all_locations, str) and all_locations.strip():
        location_items = [all_locations.strip()]
    else:
        location_items = []
    if primary_location and primary_location not in location_items:
        location_items.insert(0, primary_location)
    raw_location = "; ".join(dict.fromkeys(location_items)) or primary_location

    workplace_type = str(posting.get("workplaceType", "")).strip().casefold()
    if workplace_type in {"hybrid", "on-site", "onsite"}:
        return None
    location = raw_location
    if workplace_type == "remote" and "remote" not in location.casefold():
        location = f"{location}, Remote" if location else "Remote"

    description_parts = []
    for field_name in ("descriptionPlain", "descriptionBodyPlain", "openingPlain", "additionalPlain"):
        value = posting.get(field_name)
        if isinstance(value, str) and value.strip():
            description_parts.append(value.strip())
    if not description_parts:
        for field_name in ("description", "descriptionBody", "opening", "additional"):
            value = posting.get(field_name)
            if isinstance(value, str) and value.strip():
                description_parts.append(" ".join(re.sub(r"<[^>]+>", " ", html.unescape(value)).split()))
    lists = posting.get("lists")
    for item in lists if isinstance(lists, list) else []:
        if isinstance(item, dict):
            label = str(item.get("text", "")).strip()
            content = str(item.get("content", "")).strip()
            plain_content = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(content)).split())
            if label or plain_content:
                description_parts.append(f"{label}: {plain_content}".strip(": "))
    description = " ".join(dict.fromkeys(description_parts))[:6000]
    eligibility_evidence = global_remote_evidence(location, description)
    if not eligibility_evidence:
        return None

    url = str(posting.get("hostedUrl", "")).strip()
    if not url:
        url = f"https://jobs.lever.co/{site_slug}/{posting_id}"
    return {
        "id": f"lever_rem_{site_slug}_{posting_id}",
        "source": "Tier 3: Direct Lever public postings feed",
        "title": title,
        "company": company_label,
        "location": location,
        "work_location_status": "VERIFIED",
        "work_location_evidence": eligibility_evidence,
        "role_category": "Remote India Engineering",
        "url": url,
        "tags": [],
        "description": description,
    }
