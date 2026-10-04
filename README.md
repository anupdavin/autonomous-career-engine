# Remote India Job Search Agent

This project tracks public job listings, checks for explicit remote-from-India evidence, ranks profile evidence overlap, and prepares application materials for human review. It does not submit applications.

## Core Capabilities

- **Multi-Source Job Discovery (`job_collector.py`, `eligibility.py`)**: Polls public LinkedIn, Greenhouse, and Lever listings. A listing enters the eligible queue only when its own location text supports remote work from India or worldwide contractor eligibility, and explicit India exclusions or clear hybrid and onsite requirements are rejected. Company office locations and the legacy JSON feed are not treated as proof.
- **Deterministic Role Ranking (`reflective_agent.py`)**: Uses distinct skill and domain overlaps plus specific human feedback notes. Scores are evidence-overlap heuristics, not hiring probabilities or recruiter predictions. Legacy autopilot events are not treated as human feedback.
- **Review-Band Triage (`oracle_memory.py`)**: India-verified roles with profile overlap scores from 60 through 74 remain in the shortlist review lane. This preserves their original ranker label and score while allowing human review below the 75-point recommendation threshold.
- **Anti-Bot & Guardrail Enforcement (`guardrails.py`, `AGENTS.md`)**: Enforces strict punctuation rules (zero em-dashes or en-dashes), removes AI clichés, and validates 100% India-remote eligibility.
- **Compensation Estimates (`tax_salary_engine.py`)**: Provides rough scenario estimates. Confirm compensation and tax treatment for the actual role and contract before relying on the figures.
- **Candidate Feedback Memory (`oracle_memory.py`)**: Stores specific approval and rejection reasons. A user must add a reason before approval so future ranking has human-provided evidence.
- **Measured Adaptation (`adaptive_evaluation.py`, `oracle_memory.py`)**: Preserves the ranker's pre-review label and score, then compares them with each job's latest human role-fit decision. Results below ten examples are labeled insufficient and never change scoring weights automatically.
- **Application Preparation (`auto_applicator.py`)**: Prepares role-specific materials only for approved roles with verified India eligibility. A person reviews employer questions and submits the application.
- **Candidate Fact Gate (`candidate_fact_review.py`)**: Blocks packet generation until identity/contact, employment dates, education, work location/authorization, and resume claims each have a human review date and source reference in `candidate_fact_review.json`.
- **Application Evidence (`app_server.py`, `oracle_memory.py`)**: Records a submitted application only with receipt text and an evidence reference. Acknowledgements are separate evidence and cannot create a submission record.
- **Interactive Command Center (`app_server.py`, `dashboard_ui.html`)**: Local HTTP control server bound to loopback with a dashboard for discovery, eligibility evidence, and application status.
- **Agent Runtime Ledger (`agent_run_ledger.py`, `scheduler_24_7.py`)**: Stores run IDs, phases, heartbeats, source outcomes, terminal status, and compact error types in SQLite. A unique active-run constraint prevents two instrumented discovery cycles from running at the same time. Expired heartbeats block new runs until the operator inspects the owner process and records recovery with `python scheduler_24_7.py --recover-stale-run RUN_ID`.
- **Run Inspection API (`app_server.py`)**: `GET /api/runs` returns current runtime health and recent runs. `GET /api/runs/{run_id}` returns that run's phase events. Responses contain workflow metadata and source counts, not candidate application content.
- **Ranking Quality API (`app_server.py`)**: `GET /api/quality` reports sample coverage, confusion counts, and aggregate metrics. Reviewed roles without an original prediction snapshot are excluded and counted separately.
- **Repository Code Graph (`tools/repo_graph.py`)**: Builds a local Python AST graph with extracted import edges and explicitly inferred call edges. The graph is a navigation aid, not a full semantic index.

The default database file, `oracle_ai_local_mirror.db`, is SQLite. The current workflow continues to store its records in SQLite even if an Oracle connection succeeds. Oracle CRUD persistence is not implemented.

## Quick Start

1. Run the isolated policy, workflow, run-ledger, and ranking-evaluation checks:
   ```bash
   python -m unittest -v test_job_eligibility.py test_application_preparation.py test_job_sources.py test_agent_run_ledger.py test_adaptive_evaluation.py test_agent_control_plane.py
   ```
   `test_adaptive_pipeline.py` performs live discovery and writes database, report, and skill artifacts. It is not a routine unit test.
2. Launch the interactive dashboard server:
   ```bash
   python app_server.py
   ```
3. Run background discovery at the configured interval. This does not generate application materials:
   ```bash
   python scheduler_24_7.py --daemon
   ```
4. After `candidate_fact_review.json` has a complete source-backed review and each role has been approved, prepare application packets in a separate one-shot run:
   ```bash
   python scheduler_24_7.py --prepare-approved-materials
   ```

Packet generation only handles roles already marked approved and India-eligible. It does not upload a resume or submit an application. The preparation flag cannot be combined with daemon mode, so periodic discovery does not rewrite application packets. Keep the scheduler running in one process only.

Discovery runs are recorded in the same SQLite file as the job tracker. The dashboard refreshes runtime state while a manual scan is active and shows recent run history. An old server or scheduler started before run-ledger instrumentation does not report heartbeats to the new ledger. The dashboard disables manual scans when the server does not expose the run-ledger state. Restart it from its verified launch configuration before relying on live runtime status.

## Agent Control Plane

The repository includes a small, read-only control plane for machine-readable runtime inspection and capability discovery. It uses the observation contract defined in `agent_system/contracts.py` and the catalog in `agent_system/system_manifest.json`.

```powershell
python -m agent_system.control_plane inspect
python -m agent_system.control_plane capabilities
```

Runtime inspection includes aggregate lifecycle, evidence, and ranker feedback readiness counts plus a deterministic list of gated next actions. It can identify `APPLIED` rows without receipt evidence, point to candidate fact or role review, and show when there are too few human labels to evaluate ranking quality. Recommendations never trigger workflow execution, approvals, or ranking changes.

After restarting the updated loopback server, the same summaries are available at `GET /api/system` and `GET /api/capabilities`. The control plane does not run arbitrary commands, submit applications, send messages, or edit agent policy. See `AGENT_SYSTEM_ARCHITECTURE.md` for the workflow and boundaries.
