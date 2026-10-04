"""Pure posting-eligibility rules for the India-remote job search."""

import re


# Exclusions for onsite/hybrid or specific regions not targeted
GEOGRAPHIC_EXCLUSION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:must|require|required).{0,40}\b(?:relocate|relocation)\b",
    )
)

NON_REMOTE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bhybrid\s+(?:remote\s+)?(?:role|position|work|schedule|arrangement|model|workplace)\b",
        r"\b(?:role|position|work arrangement|working arrangement|schedule|model)\s+(?:is|will be|includes|requires)\s+(?:a\s+)?(?:hybrid|on[- ]?site|in[- ]office)\b",
        r"\b\d+\s+(?:days?|weeks?)(?:\s+per\s+(?:week|month))?\s+(?:on[- ]?site|in[- ]office)\b",
        r"\b(?:required|expected)\s+to\s+(?:work\s+)?on[- ]?site\b",
        r"\b(?:not|never|isn't|is not|cannot be|can't be|not quite)\s+(?:a\s+)?(?:100\s*%\s*remote|100\s+percent\s+remote|fully\s+remote)\b",
    )
)

RESTRICTED_REGIONS = (
    "singapore",
)

RESTRICTED_DESCRIPTION_PHRASES = (
    "must reside in singapore", "must be located in singapore",
)

REGIONAL_REMOTE_PHRASES = (
    "remote from us",
    "remote from uk",
    "remote from eu",
    "work from home",
    "work remotely",
    "remote - us",
    "remote - uk",
    "remote - eu",
)

GLOBAL_REMOTE_PHRASES = (
    "remote worldwide",
    "worldwide remote",
    "work from anywhere",
    "anywhere in the world",
    "open to candidates worldwide",
    "remote: global",
    "remote - global",
    "remote, global",
)

CONTRACT_PHRASES = (
    "independent contractor",
    "contractor",
    "b2b contract",
    "b2b contractor",
)

FULL_REMOTE_PHRASES = (
    "100% remote",
    "100 percent remote",
    "fully remote",
)


def _is_explicitly_excluded(text: str) -> bool:
    return any(pattern.search(text) for pattern in GEOGRAPHIC_EXCLUSION_PATTERNS)


def _has_non_remote_requirement(location: str, description: str) -> bool:
    if re.search(r"\bhybrid\b|\bon[- ]site\b|\bin[- ]office\b", location, re.IGNORECASE):
        return True
    return any(pattern.search(description) for pattern in NON_REMOTE_PATTERNS)


def _posting_excerpt(text: str, start: int, phrase: str) -> str:
    boundaries = (".", "!", "?", ";", "\n")
    previous = [text.rfind(mark, 0, start) for mark in boundaries]
    excerpt_start = max(previous) + 1
    following = [text.find(mark, start + len(phrase)) for mark in boundaries]
    excerpt_ends = [index for index in following if index >= 0]
    excerpt_end = min(excerpt_ends) if excerpt_ends else len(text)
    return " ".join(text[excerpt_start:excerpt_end].split())[:300]


def global_remote_evidence(location: str, description: str) -> str:
    """Return source text only when global or targeted remote eligibility is explicit."""
    location_text = " ".join(str(location or "").split())
    description_text = " ".join(str(description or "").split())
    location_lower = location_text.lower()
    description_lower = description_text.lower()
    combined_text = f"{location_text}\n{description_text}"

    # if _is_explicitly_excluded(combined_text): return ""
    if _has_non_remote_requirement(location_lower, description_lower):
        return ""
    if any(region in location_lower for region in RESTRICTED_REGIONS):
        return ""
    if any(phrase in description_lower for phrase in RESTRICTED_DESCRIPTION_PHRASES):
        return ""

    remote_terms = ("remote", "work from home", "distributed", "fully remote", "anywhere")
    if any(term in location_lower for term in remote_terms):
        return f"Posting location: {location_text}"

    if True:
        for phrase in FULL_REMOTE_PHRASES:
            phrase_start = description_lower.find(phrase)
            if phrase_start >= 0:
                excerpt = _posting_excerpt(description_text, phrase_start, phrase)
                return f"Posting location: {location_text}; official posting excerpt: {excerpt}"

    for phrase in REGIONAL_REMOTE_PHRASES:
        phrase_start = description_lower.find(phrase)
        if phrase_start >= 0:
            excerpt = _posting_excerpt(description_text, phrase_start, phrase)
            return f"Official posting excerpt: {excerpt}"

    remote_phrase = next((p for p in GLOBAL_REMOTE_PHRASES if p in description_lower), "")
    contract_phrase = next((p for p in CONTRACT_PHRASES if p in description_lower), "")
    if remote_phrase and contract_phrase:
        return f"Posting states '{remote_phrase}' and '{contract_phrase}'"

    return ""


