# Autonomous Career Engine & Global Remote Job Applicator

An autonomous, reflective career agent and application pipeline engineered for 100% remote global leadership and principal architecture roles (India EOR / Full-Time Remote and Global USD/EUR/GBP B2B Contracts).

## Core Capabilities

- **Multi-Source Job Discovery (`job_collector.py`)**: Polls public ATS boards (Greenhouse, Lever, Ashby) and remote job feeds with strict geographic and remote-eligibility filtering.
- **Reflective Pitch & Resume Tailoring (`reflective_agent.py`, `resume_vault.py`)**: Generates role-specific resumes and plain-text executive cover notes with automated critic-loop evaluation.
- **Anti-Bot & Guardrail Enforcement (`guardrails.py`, `AGENTS.md`)**: Enforces strict punctuation rules (zero em-dashes or en-dashes), removes AI clichés, and validates 100% India-remote eligibility.
- **Compensation & Tax Engine (`tax_salary_engine.py`)**: Evaluates purchasing power parity, Section 44ADA / GST export rules for B2B contracts, and India EOR net take-home pay.
- **Hybrid Memory & Skill Induction (`oracle_memory.py`, `skill_induction.py`)**: Supports Oracle AI Database 23ai/26ai (with automatic zero-overhead local SQLite fallback) and dynamic `.agent/skills` generation.
- **Live Browser Submitter & OTP Bridge (`live_browser_submitter.py`, `gmail_otp_bridge.py`, `overnight_otp_relay.py`)**: Automates ATS form completion (Greenhouse, Ashby, Lever) and handles asynchronous email verification codes.
- **Interactive Command Center (`app_server.py`, `dashboard_ui.html`)**: Local HTTP control server and dashboard UI for real-time monitoring and one-click application triggers.

## Quick Start

1. Copy `.env.example` to `.env` and `otp_relay_config.example.json` to `otp_relay_config.json` with your credentials.
2. Run the verification suite:
   ```bash
   python test_adaptive_pipeline.py
   ```
3. Launch the interactive dashboard server:
   ```bash
   python app_server.py
   ```
4. Run continuous 24/7 background polling:
   ```bash
   python scheduler_24_7.py
   ```
