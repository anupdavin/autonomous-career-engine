# Agent Work Handoff

Last reviewed: 2026-09-28

## Active objective

Support Meena Kannan's job search for 100% remote roles that can be worked from India. Keep application submissions as a person-controlled action. Confirm candidate facts before drafting or using them in an employer form.

## Current evidence

- The local API and SQLite mirror now report 79 job records, 8 India-verified roles, and 0 approved roles.
- Two rows are marked `APPLIED` in the lifecycle field.
- One row has submission receipt time and source fields. One row has acknowledgement time and source fields.
- The receipt-backed row is Elastic, job ID `gh_rem_elastic_7447426`. The saved ATS receipt text is associated by timeline event and time, not by an ID printed in the text.
- The Mastercard row is marked `APPLIED` without saved receipt evidence.
- Candidate identity, employment details, work location and authorization, education, and several technology claims still need confirmation.
- Oportun and Eltropy Senior Backend are active official India-remote listings already present in the tracker. Their saved overlap scores are 64 and 71. Both now sit in the human review lane, with their original ranker decisions unchanged.
- Everbridge has a current India, full-time, remote Java backend listing. The Lever collector is implemented in source, but the existing scheduler has not been restarted onto it.
- DXC Luxoft has a current Remote India Java integration opening, but required Apache Camel and WebFlux experience is not established. RapidCanvas requires degree equivalence and Java/Python evidence that still needs review.
- India eligibility now uses a standalone policy module that rejects explicit India exclusions and clear hybrid or onsite requirements. Thirteen isolated eligibility cases pass. The live scheduler process still has the previously imported policy until it is restarted.
- The Git workspace had 189 pre-existing changed entries at review time. Do not revert or overwrite them without checking ownership and purpose.

## Safe next actions

1. Obtain and record candidate fact confirmations, then update the canonical profile with a source for each fact.
2. Review the five India-verified roles against live official listings. Exclude roles that are not 100% remote and India-eligible.
3. Prepare role-specific materials only after the role and candidate facts are approved.
4. For any actual submission, save the ATS receipt text, stable evidence reference, timestamp, and job ID. Record employer acknowledgement only from its own evidence.
5. Inspect `ARCHITECTURE_REVIEW.md` and `AGENT_FEATURES.json` before continuing architecture work.

## Runtime cautions

- The dashboard runs on loopback and the scheduler is a separate process.
- The running scheduler process loaded older code that still calls application preparation after discovery. Source edits do not change that process. A controlled restart is needed before discovery and preparation are separated at runtime. The live API currently reports zero approved roles.
- Standalone browser helpers can upload candidate resumes to employer forms, and the OTP relay can follow Gmail forwarding links and write codes to disk. Do not run either until candidate facts and each external action have explicit review.
- Do not approve Antigravity or operating-system permissions through this repository workflow. Use the user-facing permission controls when a permission request is actually visible.
- Do not submit an application, send a recruiter message, or use an unverified candidate claim without the user's authorization and reviewed source material.

## Engineering update, 2026-09-28

- Discovery and application-material preparation are separate commands. `--prepare-approved-materials` is an explicit one-shot action and is rejected with `--daemon`, preventing repeated packet rewrites. It does not submit applications.
- Both the scheduler gate and the packet writer now require a complete, source-backed `candidate_fact_review.json`. Its initial entries are all unverified, so packet generation is blocked until Meena reviews and records the required facts. This does not mark facts as true by itself.
- Preparation returns a structured status, summary, next actions, and artifact paths. Failures identify the exception and instruct the operator to inspect partial output before retrying.
- Added isolated tests for the candidate fact gate, explicit opt-in, daemon conflict, empty results, and failures. The 15 eligibility cases and two source configuration cases also pass, for 26 passing tests total.
- The running scheduler process loaded the previous code before this change. Discovery and preparation remain coupled in that process until a controlled restart. Launch metadata confirms the script name and daemon flag, but not its workspace path or working directory. No scheduled task was found, and no process was restarted.
- The repo graph was generated using the existing local AST graph tool, then queried for the scheduler-to-preparation path. This is a scoped local implementation inspired by Graphify's query, path, and source-provenance approach, not the Graphify package itself.
- The exact Graphify package and version were verified against the linked upstream repository. Its documented code-only command was attempted with a workspace-local cache, but sandbox network policy denied the PyPI socket. No package source was downloaded, installed, or executed. The existing local graph tool remains the available fallback.
- Fresh official listing checks at 09:16 SGT on 2026-09-28 confirmed the Oportun, Eltropy Senior, RapidCanvas, and DXC Luxoft application pages remained active. Oportun and Eltropy were later ingested into the tracker by discovery.

## Agent runtime engineering update, 2026-09-28

- Added a durable SQLite run ledger for discovery. It records a run ID, workflow, phase, heartbeat, terminal status, compact statistics, and source-level result counts. It does not persist job descriptions, candidate contact details, or application packet text.
- Added a database uniqueness constraint for a single instrumented active run. Runs without a heartbeat past the configured threshold are marked stale and block new runs. After inspecting the owner process, an operator can record recovery with `python scheduler_24_7.py --recover-stale-run RUN_ID`. The ledger reports the owning process ID.
- Discovery now emits source outcomes and progress events. The daemon retries failed cycles with bounded backoff and retains the error class in the run record.
- Added read-only `/api/runs` and `/api/runs/{run_id}` endpoints and a dashboard runtime panel with phase, heartbeat, source counts, errors, and recent run history.
- Added pre-review `ranker_decision` snapshots. Human feedback remains the training label, while later rescoring preserves the original decision and score for an existing human-reviewed role. `adaptive_evaluation.py` reports aggregate confusion metrics against the latest label and excludes missing snapshots.
- Added `/api/quality` and a dashboard feedback panel. Metrics are marked insufficient below ten examples, and the agent does not auto-tune ranking weights from this small local feedback set.
- The scoped verification suite now has 34 passing cases across eligibility, preparation, source configuration, run lifecycle, stale recovery, and feedback evaluation.
- The live server and scheduler were not restarted. Processes already running older code do not write to this new ledger, so the dashboard will show instrumented run state only after the updated process starts. No external permission or Antigravity session was changed.
- Live surface check: the API at `127.0.0.1:8080/api/runs` returns 404, confirming the current server has not loaded the new route. Process PIDs 16580 and 22360 remain from the earlier app and scheduler sessions. `agy.exe` is present, but an `agy` CLI command is not on PATH. No restart or session steering was attempted because the verified launch path and CLI are unavailable.
- The Graphify repository confirms the official PyPI package name is `graphifyy`, and upstream documents a code-only local extraction path. The package itself has not yet been executed because the sandbox blocks PyPI network access. The repository's deterministic local Python graph remains available until a project-local Graphify extraction completes.
- Rebuilt and queried the local AST code graph after the changes. It contains 214 nodes and 528 edges with zero parse errors. The graph is a local fallback, not the upstream Graphify package.

## Job search update, 2026-09-28 10:38 SGT

- Rechecked the local database and running `/api/state`: 79 role records, 2 lifecycle rows marked `APPLIED`, 1 receipt-backed submission, 1 acknowledgement, 8 India-verified roles, 0 approved roles, and 0 interviews. The acknowledgement is tied to the same Elastic receipt. The Mastercard `APPLIED` row has no receipt evidence.
- Reopened the official Oportun R14037, Eltropy Senior Backend Engineer, and Everbridge Senior Software Engineer Backend and AI-Enabled pages. All remain open with India remote scope. Everbridge's Lever page labels the role India, full time, and remote.
- Oportun and Eltropy scores of 64 and 71 were below the 75 recommendation cutoff and had been automatically closed as `DEAD_ZONE`, despite verified India-remote evidence. Added a review band for verified roles scoring 60-74 and returned only these two automatically filtered records to `SHORTLISTED` with audit timeline events. Scores, ranker decisions, application evidence, and approval status are unchanged.
- Added public Lever feed discovery for Everbridge, Lingaro, and HighLevel using Lever's published-postings API. Parsing is separated from networking and tested against India-remote, hybrid, non-India, and non-engineering cases. The active scheduler has not been restarted, so Lever discovery will start after a verified restart.
- Candidate fact review remains 0 of 5 groups. No resume packet was generated, no employer form was opened or submitted, and no message was sent.
- Focused verification passed 48 tests before this handoff update. The local code graph was refreshed to 259 nodes and 620 edges with zero parse errors.

## Agent control-plane update, 2026-09-28

- Added a versioned capability catalog and stable observation contract with `status`, `summary`, `next_actions`, `artifacts`, and `details` fields.
- Added read-only control-plane commands for capability discovery and runtime inspection. Runtime inspection reads run metadata, aggregate job progress, ranker feedback readiness, candidate fact review counts, and graph health. It does not return candidate facts or application content.
- Added `GET /api/system` and `GET /api/capabilities` to the loopback server. They become available after the server is restarted from the verified workspace launch path.
- The agent-callable catalog is read-only. Job discovery and packet preparation remain gated operator workflows. Application submission, recruiter messaging, arbitrary shell execution, and automatic ranking policy changes remain disabled.
- Added `AGENT_SYSTEM_ARCHITECTURE.md` and linked it from the repository instructions and README. It records the workflow, action boundaries, current gaps, and staged engineering gates.
- Refreshed the local AST graph after the additions. It contains 243 nodes and 588 edges with zero parse errors. The new path from the app API to runtime inspection is traced in the graph.
- Six focused control-plane tests pass, Python syntax compilation passes, and both control-plane CLI commands produce the required observation shape. The live app server was not restarted; its new routes are source-verified but not active in the running process.

## Adaptive readiness inspection, 2026-09-28

- Extended the read-only control-plane summary with aggregate lifecycle, India-eligibility, shortlist, approval, submission-receipt, and acknowledgement counts. No job descriptions or candidate details are returned.
- The current SQLite mirror has 79 job rows, 8 India-verified roles, 7 India-verified shortlisted roles, 0 approved roles, 2 `APPLIED` lifecycle rows, 1 receipt-backed submission, and 1 acknowledgement.
- The inspection identifies 1 `APPLIED` row without saved receipt evidence and recommends reconciling it. The acknowledgement is linked to the receipt-backed row.
- The usable human role-fit evaluation sample is 0, below the 10-label threshold. Ranking feedback is not measured, and no weights are changed automatically.
- Next-action recommendations respond to missing candidate fact review, receipt evidence gaps, ranker sample sufficiency, eligible shortlist rows, partial or stale discovery runs, and missing India-verified roles. The control plane only recommends actions and does not execute them.
- A read-only CLI inspection returned a valid manifest, a 259-node and 622-edge local graph with no parse errors, and a partial latest discovery run. Candidate fact review remains 0 of 5 groups.
- `graphifyy` is not installed in the workspace runtime. The repository continues to use its deterministic Python AST graph, following Graphify's query and provenance ideas without claiming upstream Graphify coverage.
- Added a dashboard readiness panel that consumes `GET /api/system`, shows only aggregate counts, and labels its next actions as recommendations. The live server returned 404 for that route, so the panel will activate after a restart from the verified launch configuration.
- Refreshed and queried the local graph after the readiness integration. The control-plane path to the ranker evaluator is present, and the graph has 259 nodes, 622 edges, and no parse errors.
- Python AST parsing, JSON parsing, dashboard JavaScript syntax checking, and the workspace text guardrail scan passed. No test suite was run in this update.
- No server or scheduler was restarted. Candidate fact review remains incomplete, and application-material preparation remains gated.
