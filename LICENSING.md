# Licensing, attribution and package boundaries

**Software:** MIT License, `LICENSE`, copyright © 2026 Aadhityaa Mohanavelu.
**Original questionnaires and documentation:** CC BY 4.0, `LICENSE-CONTENT.md`,
copyright © 2026 Aadhityaa Mohanavelu (subject to actual rights ownership).
**Associated research:** Aadhityaa Mohanavelu and Khalid K. Osman, Research
Square preprint https://doi.org/10.21203/rs.3.rs-10888037/v1.

| File scope | Terms | Scope qualification |
| --- | --- | --- |
| `src/`, `tools/`, `tests/`, `run_*.py`, `score_core8.py`, `survey_readiness.py` | MIT | Toolkit-authored software, excluding third-party code |
| `config/`, functional machine-readable model/predictor configurations | MIT | This does not license the scientific publication or private data |
| `survey/*.docx`, `survey/*.pdf`, codebooks, `questionbook/`, instrument specifications in `spec/` | CC BY 4.0 | Original content for which the licensor has redistribution rights |
| `docs/`, `README.md`, guidance, original templates and synthetic example content | CC BY 4.0 | Material created for this toolkit; third-party content excluded |
| `survey/WSQS_International_Calculator.xlsx` | Mixed MIT + CC BY 4.0 | Executable original scoring formulas under MIT, original survey/content under CC BY |
| `environment/` and dependencies | Upstream licenses where relevant | Dependency listings do not relicense third-party software |
| `CITATION.cff` | Citation metadata | Citation requests are distinct from copyright permissions |
| Frozen original-study reproducibility ZIP | **Excluded** | Separate archive and separate rights assessment before distribution |
| Private household data, synthetic QA bundles and installation logs | **Not included in public package** | Do not add private records or private QA folders to GitHub |

No source-code license is intended to alter the core scoring specification,
model behavior, methodological limitations or original study's recorded results.
Researchers using the toolkit should cite the associated work and the toolkit
version. The Research Square DOI is the **paper DOI**, not a software DOI.

The licenses grant only rights actually held by the applicable licensor and
cannot waive institutional, third-party, privacy or consent obligations.
