# Submission Evidence Audit

Checked on 2026-10-04 using the local ATS screenshots and current official postings.

## Receipt evidence

- The primary SQLite tracker has two receipt-backed records: Elastic Consulting Architect - Platform and Eltropy Senior Backend Engineer.
- `easy_apply_submission_results.json` has ten rows labelled `CONFIRMED_SUBMITTED`. The saved screenshots for rows 1 and 3 through 10 show employer success screens. Row 2 shows the job details screen without a receipt, so its status is now `SUBMITTED_UNVERIFIED`. Its prior status and the reason for review are retained in the JSON record.
- The Elastic row in that JSON duplicates the Elastic record already in SQLite. Across both sources, there are ten unique roles with visible employer receipt evidence, including Eltropy.

## India remote eligibility

- Verified from the official posting: Cyberhaven Staff/Principal Software Engineer, AI Security; Cyberhaven Senior Software Engineer, MacOS Endpoint; Oscilar JavaScript Developer, Web SDK; Elastic Consulting Architect - Platform; and Eltropy Senior Backend Engineer.
- The Cyberhaven MacOS role asks for Swift and native macOS endpoint experience. The Oscilar role is a JavaScript Web SDK role. Both have receipts but are weaker matches to Meena's verified Java backend history.
- The SigNoz Staff Backend screenshot lists India but does not show remote work mode.
- The Cyberhaven Platform screenshot lists Bangalore and EU Remote. Work from Chennai is not established.
- The Juniper Square Technical Lead and QA Automation Lead screenshots list India, but the saved evidence does not establish remote work for those exact posting IDs.
- The Juniper Square Senior Staff Software Engineer, Data receipt is real, but the official application page limits location to the Americas (USA or Canada). It does not count toward the India-eligible goal.

## Repository handling

- Dashboard projection now requires a confirmed status and an existing receipt file before an auxiliary row appears as `APPLIED`.
- Rows without receipt fields display as unverified. Imported global rows no longer receive synthetic receipt timestamps or default India-remote status.
- The Antigravity CLI status check could not read its conversation because the CLI is logged out in this shell. The job search continued from official employer pages.
