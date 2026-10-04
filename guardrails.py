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

SLOPPY_AI_CLICHES = (
    "delve", "testament to", "thrilled to", "seamless", 
    "game-changer", "synergy", "moreover", "furthermore",
    "in today's rapidly evolving", "look no further",
    "you're absolutely right", "you are absolutely right",
    "great point", "i completely agree", "that makes sense",
    "i apologize for", "sorry about that", "without further ado",
    "let's dive in", "hope this helps", "in conclusion"
)

def assert_no_sloppy_ai(text: str, context_label: str = "output") -> None:
    """
    Hook/Guardrail: Enforces absolute accountability and respect for client time by 
    strictly rejecting any text that contains lazy, generic, or obvious AI cliches.
    We must never be found using sloppy AI.
    """
    if not text:
        return
    text_lower = text.lower()
    for cliche in SLOPPY_AI_CLICHES:
        if cliche in text_lower:
            raise AssertionError(
                f"[Accountability Violation] Sloppy AI cliche '{cliche}' detected in {context_label}. "
                "We do not waste the client's time with generic fluff."
            )
