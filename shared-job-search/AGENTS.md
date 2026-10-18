# Shared search agent handoff

Follow the user's latest explicit job-search instructions. For this shared dataset, the user explicitly includes Singapore onsite/hybrid, worldwide remote, Singapore/India remote and promising country-unconfirmed remote leads. This supersedes the repository root's narrower remote-only geographic rule for this folder. Do not change the existing runtime's eligibility filters or SQLite workflow as part of ledger maintenance.

1. Read README.md, POLICY.md, jobs.json and reported.jsonl from the latest default branch first. Compare existing runtime job records/application drafts if available. Historical coverage is incomplete.
2. Treat every historically_reported event as already alerted even if reported_at is null. Do not re-alert a role solely because it was refreshed, moved ATS, renamed or copied by a recruiter.
3. Use one canonical job with separate anup/meena assessments. Match employer, client/project, requisition, URL aliases and substantially identical descriptions. Preserve aliases and old evidence on merges. Mactores variants are one project.
4. Import dates are not verification dates. Never replace an old verification date with today's date unless the source was reopened. Record source URL, exact check time/date, observed status, arrangement, compensation and any failed form check.
5. Distinguish source eligibility from personal authorization. Hard residence/authorization restrictions remain visible. India onsite/hybrid is excluded. Do not presume relocation. Country-unconfirmed remote leads remain valid exploratory leads.
6. Both candidates know Apache Camel. Missing resume keywords are preparation/assessment points, not assumed inability. No invented employers, tenure, certifications, metrics, production ML or production AI-agent claims.
7. Published salary only; unknown stays unknown. Do not import this repository's scenario estimates/default pay or tax assumptions into employer pay. Record original currency/period/geography and separate equity/bonus. Any SGD comparison requires authoritative dated FX and an applicable established pay period. Contract revenue is separate from employee salary.
8. Never label a shortlist as approved/applied without user decision or submission evidence. No applications, employer/recruiter messages, invitations or permission changes.
9. Parallel workers use branches and PRs. Re-read current head before changes; preserve current blob SHA and reject conflicts. Never force-push or replace unrelated files. Keep report events and job data consistent. Verify the saved GitHub files after publishing.
10. A new role alert requires current evidence and candidate-specific truthful tailoring. Alert only worthwhile new matches; no padding. Use up to 10 per candidate. Preserve scope, hours, contract/compensation questions and failed verification explicitly.
11. Write plain language, no em/en dashes. Run validate.py after changes. Update both readable indexes when jobs change.
12. Do not spawn agents merely because this file supports collaboration. Delegation requires explicit user authorization or another applicable instruction.
