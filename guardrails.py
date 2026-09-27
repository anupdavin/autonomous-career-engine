import re

FORBIDDEN_DASH_CHARS = ("\u2014", "\u2013", "\u2015", "&mdash;", "&ndash;", "&#8212;", "&#8211;")


def sanitize_no_emdashes(text: str) -> str:
    """
    Hard Guardrail: Strips all Unicode em-dashes (U+2014), en-dashes (U+2013),
    horizontal bars (U+2015), and HTML dash entities, replacing them with natural
    human punctuation (commas or standard ASCII hyphens).
    """
    if not text:
        return text
    cleaned = text
    # Replace spaced em-dash / en-dash with a standard ASCII hyphen or comma
    cleaned = re.sub(r"\s*[\u2014\u2015]\s*", ", ", cleaned)
    cleaned = re.sub(r"\s*\u2013\s*", " - ", cleaned)
    for entity in ("&mdash;", "&ndash;", "&#8212;", "&#8211;"):
        cleaned = cleaned.replace(entity, " - ")
    # Clean up any accidental double commas or comma-period
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r",\s*\.", ".", cleaned)
    return cleaned


def assert_no_emdashes(text: str, context_label: str = "output") -> None:
    """
    Raises an AssertionError if any em-dash or en-dash exists in `text`.
    """
    for ch in FORBIDDEN_DASH_CHARS:
        if ch in text:
            raise AssertionError(
                f"[Guardrail Violation] Forbidden dash character ({repr(ch)}) detected in {context_label}!"
            )
