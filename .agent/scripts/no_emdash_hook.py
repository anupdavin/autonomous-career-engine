import json
import sys
from pathlib import Path


def strip_emdashes(val: str) -> str:
    return (
        val.replace("\u2014", " - ")
        .replace("\u2013", " - ")
        .replace("\u2015", " - ")
        .replace("&mdash;", " - ")
        .replace("&ndash;", " - ")
    )


def main() -> None:
    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return

    tool_call = payload.get("toolCall", {})
    args = tool_call.get("args", {})
    overwrites = {}

    for key in ("CodeContent", "ReplacementContent"):
        if isinstance(args.get(key), str) and any(d in args[key] for d in ("\u2014", "\u2013", "\u2015")):
            overwrites[key] = strip_emdashes(args[key])

    if overwrites:
        print(
            json.dumps(
                {
                    "decision": "allow",
                    "reason": "Auto-sanitized forbidden em-dashes/en-dashes via PreToolUse guardrail hook.",
                    "overwrite": overwrites,
                }
            )
        )
    else:
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
