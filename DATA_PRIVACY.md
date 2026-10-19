# Data privacy and responsible reuse

This repository contains **no observed household-level survey records** from the original Tamil Nadu study. The files `example/synthetic25.csv` and `example/expected_scores.csv` are synthetic software demonstrations, **not** research respondents or empirical model results. The empty Excel workbook is a template.

## Researchers using the toolkit

- Keep completed questionnaires, private Excel copies, respondent-level CSV exports, individual predictions, trained models containing sensitive information and approval documents **outside this Git repository**.
- Run `tools/extract_research_entry.py`, `survey_readiness.py` and forecasting commands with confidential output paths. Do not upload their respondent-level outputs or logs to a public repository.
- Review ethics, consent, local data-protection requirements and de-identification before collecting or sharing information. Record IDs can still be linkable identifiers when a private key exists.
- Before each push, inspect both tracked and untracked files using `git status --short`, `git diff --cached --name-only` and `git ls-files`. `.gitignore` cannot protect a file explicitly forced into the repository or already tracked.
- Review document metadata and the contents of generated examples before publication. Do not assume an output is synthetic merely because its filename contains “demo.”

## Release scope

The separate original-study reproducibility archive is **not bundled** with this international toolkit, and it has its own release approval and scientific scope. This toolkit does not include original-study observed records or original-study private QA artifacts.

The scoring framework is a research instrument. The internationally adapted questionnaire has not yet been independently validated for all settings; local validation and ethical review are necessary before field use.
