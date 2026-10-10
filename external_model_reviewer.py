"""
external_model_reviewer.py
Standalone multi-provider reviewer for application packets using non-Gemini models.
Supported Providers:
  1. anthropic   (Claude 3.5 Sonnet / Claude 3.7 Sonnet via ANTHROPIC_API_KEY)
  2. openai      (GPT-4o / GPT-4.1 via OPENAI_API_KEY)
  3. groq        (Llama 3.3 70B via GROQ_API_KEY - free high-speed tier)
  4. openrouter  (Access to Claude, DeepSeek, Llama via OPENROUTER_API_KEY)
  5. ollama      (Local Llama 3 / Mistral / DeepSeek via http://localhost:11434)
"""

import argparse
import json
import os
import sys
from pathlib import Path
import httpx

BASE_DIR = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
PACKETS_PATH = BASE_DIR / "application_drafts" / "prepared_packets_2026-10-04.json"
FACTS_PATH = BASE_DIR / "candidate_fact_review.json"
AGENTS_MD_PATH = BASE_DIR / "AGENTS.md"
OUTPUT_REPORT_PATH = BASE_DIR / "application_drafts" / "external_model_review_report.md"

AUDIT_PROMPT_TEMPLATE = """CRITICAL INSTRUCTION: Review and critique the following job application packet immediately. Do NOT reply with a conversational acknowledgment or prelude. Output your complete evaluation report directly now, structured under the 4 sections requested below.

Strict Workspace Guardrails to Verify:
1. Punctuation: STRICTLY FORBID Unicode em-dashes (U+2014), en-dashes (U+2013), horizontal bars (U+2015), and HTML dash entities (&mdash;, &ndash;). Standard ASCII hyphens (-) are permitted.
2. Anti-Cliché / Human Authenticity: Strictly forbid AI filler vocabulary ('delve', 'testament to', 'thrilled to', 'seamless', 'game-changer', 'synergy', 'moreover', 'furthermore'). Plain-text first-person senior engineer prose only. No markdown bolding inside message blocks.
3. Candidate Facts Verification:
   - Full Name: Meena Kannan
   - Experience: 9+ years in production distributed systems
   - Core Tech: Java 21, Spring Boot 3, AWS EKS, Istio mTLS, Apache Kafka, Redis, Spring AI, MCP
   - Current Role: NCS Singapore (VRLS 2.0 public sector modernisation project)
   - Location: Chennai, India (100% remote, global B2B contract or India EOR)
   - Notice Period: 60 days
4. Target Geographic Scope: Must be 100% Remote globally (Worldwide, US, EU, UK, India). STRICTLY NO Singapore onsite or Singapore hybrid roles.

Application Packet to Audit:
- Target Company: {company}
- Target Role: {title}
- Target Location: {location}
- Track: {track}
- Selected Resume: {resume_name}
- Application URL: {url}

Cover Note Text:
\"\"\"
{cover_note}
\"\"\"

Please provide your rigorous critique now:
1. Guardrail Compliance: Did you find any em-dashes, en-dashes, AI clichés, or excessive bolding?
2. Factual Accuracy: Are all claims realistic, senior-level, and aligned with candidate facts?
3. Role & Pitch Alignment: How compelling is the cover note and resume selection for this specific role?
4. Final Score (0-100) and Verdict: [APPROVED] or [REVISION_REQUIRED] (provide exact changes if revision is needed).
"""


def call_anthropic(api_key: str, model: str, prompt: str) -> str:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": model or "claude-3-5-sonnet-20241022",
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = httpx.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=60.0)
    if r.status_code != 200:
        raise RuntimeError(f"Anthropic API Error ({r.status_code}): {r.text}")
    data = r.json()
    return data["content"][0]["text"]


def call_openai_compatible(endpoint: str, api_key: str, model: str, prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a Senior Principal Engineering and Talent Auditor."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    r = httpx.post(endpoint, headers=headers, json=payload, timeout=60.0)
    if r.status_code != 200:
        raise RuntimeError(f"API Error ({r.status_code}): {r.text}")
    data = r.json()
    return data["choices"][0]["message"]["content"]


def call_codex_cli(prompt: str, model: str = "") -> str:
    import subprocess
    import tempfile
    import uuid
    
    tmp_out = BASE_DIR / "application_drafts" / f"codex_eval_{uuid.uuid4().hex[:8]}.txt"
    cmd = ["codex.cmd", "exec", "--ephemeral", "-o", str(tmp_out), prompt]
    if model:
        cmd.extend(["-m", model])
    try:
        res = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=240
        )
        if tmp_out.exists():
            content = tmp_out.read_text(encoding="utf-8", errors="replace").strip()
            tmp_out.unlink()
            return content
        if res.returncode != 0:
            raise RuntimeError(f"Codex CLI failed (exit {res.returncode})")
        return "No output captured from Codex CLI."
    except Exception as e:
        if tmp_out.exists():
            try:
                tmp_out.unlink()
            except Exception:
                pass
        raise e


def call_ollama(model: str, prompt: str) -> str:
    payload = {
        "model": model or "llama3",
        "prompt": prompt,
        "stream": False
    }
    r = httpx.post("http://localhost:11434/api/generate", json=payload, timeout=90.0)
    if r.status_code != 200:
        raise RuntimeError(f"Ollama Error ({r.status_code}): {r.text}")
    return r.json()["response"]


def clean_dashes(text: str) -> str:
    return text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2015", "-").replace("&mdash;", "-").replace("&ndash;", "-")


def main():
    parser = argparse.ArgumentParser(description="Audit application packets with non-Gemini models.")
    parser.add_argument(
        "--provider",
        choices=["codex", "anthropic", "openai", "groq", "openrouter", "ollama"],
        default="codex",
        help="LLM Provider to use (default: codex)"
    )
    parser.add_argument("--model", type=str, default="", help="Model name (e.g. claude-3-5-sonnet-20241022, gpt-4o, llama-3.3-70b-versatile, llama3)")
    parser.add_argument("--api-key", type=str, default="", help="API key (defaults to env var based on provider)")
    parser.add_argument("--role-index", type=int, default=0, help="Index of the packet to review (0-21). Default is 0.")
    parser.add_argument("--all", action="store_true", help="Review all 22 packets instead of just one.")
    args = parser.parse_args()

    if not PACKETS_PATH.exists():
        print(f"Error: Packets file not found at {PACKETS_PATH}")
        sys.exit(1)

    packets = json.loads(PACKETS_PATH.read_text(encoding="utf-8"))
    print(f"Loaded {len(packets)} application packets.")

    targets = packets if args.all else [packets[args.role_index]]

    # Determine API key
    key = args.api_key
    if not key:
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY"
        }
        env_var = env_map.get(args.provider)
        if env_var:
            key = os.environ.get(env_var, "")

    if args.provider not in ("ollama", "codex") and not key:
        print(f"\n[!] Missing API key for provider '{args.provider}'.")
        print(f"    Please either pass --api-key <YOUR_KEY> or set the {env_map.get(args.provider)} environment variable.")
        print(f"    Example: $env:{env_map.get(args.provider)}='your_key_here'\n")
        sys.exit(1)

    results = []
    for idx, p in enumerate(targets, 1 if args.all else args.role_index + 1):
        print(f"\n[{idx}/{len(packets)}] Auditing {p['company']} - {p['title']} with {args.provider}...")
        prompt = AUDIT_PROMPT_TEMPLATE.format(
            company=p["company"],
            title=p["title"],
            location=p["location"],
            track=p["track"],
            resume_name=p["resume_name"],
            url=p["url"],
            cover_note=p["cover_note"]
        )

        try:
            if args.provider == "codex":
                critique = call_codex_cli(prompt, args.model)
            elif args.provider == "anthropic":
                m = args.model or "claude-3-5-sonnet-20241022"
                critique = call_anthropic(key, m, prompt)
            elif args.provider == "openai":
                m = args.model or "gpt-4o"
                critique = call_openai_compatible("https://api.openai.com/v1/chat/completions", key, m, prompt)
            elif args.provider == "groq":
                m = args.model or "llama-3.3-70b-versatile"
                critique = call_openai_compatible("https://api.groq.com/openai/v1/chat/completions", key, m, prompt)
            elif args.provider == "openrouter":
                m = args.model or "anthropic/claude-3.5-sonnet"
                critique = call_openai_compatible("https://openrouter.ai/api/v1/chat/completions", key, m, prompt)
            elif args.provider == "ollama":
                m = args.model or "llama3"
                critique = call_ollama(m, prompt)
            else:
                critique = "Unknown provider"

            critique_clean = clean_dashes(critique)
            print("--- Review Verdict ---")
            print(critique_clean[:500] + ("..." if len(critique_clean) > 500 else ""))
            results.append({
                "role_id": p["role_id"],
                "company": p["company"],
                "title": p["title"],
                "model": f"{args.provider}:{args.model or 'default'}",
                "critique": critique_clean
            })
        except Exception as e:
            print(f"[!] Error during review: {e}")
            results.append({
                "role_id": p["role_id"],
                "company": p["company"],
                "title": p["title"],
                "model": f"{args.provider}:{args.model or 'default'}",
                "error": str(e)
            })

    # Save to report file
    report_lines = [
        f"# External Non-Gemini Model Review Report\n",
        f"- Provider: {args.provider}",
        f"- Packets Audited: {len(results)}\n",
        "---\n"
    ]
    for r in results:
        report_lines.append(f"## {r['company']} - {r['title']}")
        if "error" in r:
            report_lines.append(f"**Audit Error:** {r['error']}\n")
        else:
            report_lines.append(f"**Model:** {r['model']}\n")
            report_lines.append(f"{r['critique']}\n")
        report_lines.append("---\n")

    OUTPUT_REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n[+] Full review report saved to: {OUTPUT_REPORT_PATH}")


if __name__ == "__main__":
    main()
