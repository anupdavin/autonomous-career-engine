# Shared job search: Anup and Meena

This folder is the shared handoff and deduplication ledger for the public-web job search. It contains 100 distinct listing records reconstructed from the 57-role complete tracker dated 16 October 2026 and 44 later alert records, with one exact-URL overlap merged. The Mactores full-time/freelance variants are one project with alternate URLs.

## Start here

- [jobs.json](jobs.json): canonical job records, source URLs, historical verification, published pay, restrictions, and separate candidate assessments.
- [ANUP.md](ANUP.md) and [MEENA.md](MEENA.md): readable indexes. Alphabetical indexes are not new rankings; original priority tiers remain in JSON.
- [reported.jsonl](reported.jsonl): shared alert history. Every imported job has already been reported. Null alert timestamps mean unavailable, not unreported.
- [AGENTS.md](AGENTS.md): collaboration, scope, verification and update rules.
- [POLICY.md](POLICY.md): candidate positioning and search/compensation rules.
- `python shared-job-search/validate.py`: validate record identity, required data, aliases and alert references. No network calls or writes.

## Import boundaries

This is a historical migration on 18 October 2026, not a new check of 100 live vacancies. A status marked open describes the last recorded check. Source dates and incomplete application checks are retained. Reopen actual employer/application pages before a new application recommendation. Closed and uncertain records stay in the ledger to prevent rediscovery spam.

Coverage is limited to recovered tracker data and available conversation alerts. Earlier conversations and this repository's independent SQLite database/application drafts may contain more jobs. Compare those before claiming complete historical deduplication. Existing SQLite approval/submission records are not imported, overwritten or inferred here. No row imported here means the user approved or submitted an application.

## Collaboration

Read this folder from the latest default branch before discovery. Use the same job for both candidates with separate assessments. Deduplicate by employer, end client/project, requisition, aliases and substantially identical description, not just URL or title. Preserve one shared record and append evidence/status history. Refresh timestamps do not make a role new.

For concurrent work, use a distinct branch per worker and a pull request, then rebase/re-read before merging. Never overwrite the entire ledger from a stale copy. Use the current GitHub file SHA for updates. Do not force-push. Keep jobs.json and reported.jsonl in one logical commit when recording a new alert. Record an alert only after it was actually delivered; a proposed alert is not reported. Preserve historical events and user application decisions.

This folder is a file-based collaboration interface. It is not automatically connected to the existing SQLite runtime, app dashboard or application preparation pipeline. Agents must read it explicitly. No additional daemon, application submission, recruiter contact or external publication is authorized by this import.
