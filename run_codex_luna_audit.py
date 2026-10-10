import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
PROMPT_FILE = BASE_DIR / "application_drafts" / "codex_review_prompt.md"
OUTPUT_FILE = BASE_DIR / "application_drafts" / "codex_luna_review_report.md"

if not PROMPT_FILE.exists():
    print(f"Error: Prompt file not found at {PROMPT_FILE}")
    sys.exit(1)

prompt_text = PROMPT_FILE.read_text(encoding="utf-8")
print(f"Loaded prompt ({len(prompt_text)} chars). Launching Codex CLI with gpt-6-luna and max effort...")

cmd = [
    "codex.cmd",
    "exec",
    "--ephemeral",
    "-o",
    str(OUTPUT_FILE),
    "-c",
    'model="gpt-6-luna"',
    "-c",
    'model_reasoning_effort="max"',
    "-"
]

try:
    proc = subprocess.run(
        cmd,
        input=prompt_text,
        text=True,
        capture_output=True,
        timeout=600,
        encoding="utf-8",
        errors="replace"
    )
    print("Codex process completed.")
    print("Returncode:", proc.returncode)
    if proc.stderr:
        # print first few lines of stderr for info
        err_lines = [line for line in proc.stderr.splitlines() if line.strip()][:10]
        print("Stderr snippet:\n" + "\n".join(err_lines))
        
    if OUTPUT_FILE.exists():
        content = OUTPUT_FILE.read_text(encoding="utf-8", errors="replace").strip()
        print(f"\nReport written successfully ({len(content)} chars).")
        print("\n--- Summary Snippet ---")
        print(content[:600] + ("..." if len(content) > 600 else ""))
    else:
        print("Error: Output file was not created.")
        if proc.stdout:
            print("Stdout snippet:\n", proc.stdout[:500])
except subprocess.TimeoutExpired:
    print("Error: Codex CLI timed out after 600 seconds.")
except Exception as e:
    print(f"Exception during execution: {e}")
