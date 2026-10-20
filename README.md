# Water Service Quality Score (WSQS) | International Research Toolkit

Developed by **Aadhityaa Mohanavelu** as part of research conducted in the **Osman Lab at Stanford University**, under the supervision of **Prof. Khalid K. Osman**.

**Version 0.9.0.** This package combines original CORE-8 scoring, the 43-item adapted research survey (plus three optional sensitivity questions), Excel data entry and new-data Python analysis. Its international wording is **not independently validated**. Obtain local consent, ethics approval and relevant redistribution rights before field administration.

## Where to begin

Open `survey/WSQS_International_Calculator.xlsx` in Microsoft Excel. `MY WSQS` scores one household, `BATCH CORE8` scores up to 100 and `RESEARCH ENTRY` collects 43 research questions with three optional sensitivity questions for up to 100 rows. `CORE8 QUESTIONS` gives full question wording and response choices. CORE-8 averages valid applicable domains on a 0–100 scale. More than zero but fewer than seven applicable answered domains produce a score **flagged LOW COVERAGE**; zero applicable answers yield no score. Structural Customer Service nonapplicability is distinct from poor service.

Printable survey masters are in `survey/`; the CSV crosswalk documents original wording, international adaptations and native coding. Word and PDF questionnaires use a black-on-white academic presentation. Teams must complete the study-specific consent template before use.

## Python setup

Use the Python environment in `environment/` and run `PYTHONPATH=src python -m unittest discover -s tests -v`. Independent analyses use `run_toolkit.py`, `run_advanced.py` and `survey_readiness.py`. To export respondent answers from a **private** completed workbook:

    python tools/extract_research_entry.py --input /private/completed.xlsx --output /private/export_01
    python survey_readiness.py --input /private/export_01/PRIVATE_RESEARCH_RESPONSES.csv --output /private/readiness_01
    python run_toolkit.py --input /private/export_01/PRIVATE_RESEARCH_RESPONSES.csv --output /private/descriptive_01 --analysis descriptive

The exported CSV contains private respondent-level information. **Never upload it to an open repository.** Python descriptives now also report scored-at-least-seven, low-coverage and structural Customer Service N/A counts, alongside domain means.

## Forecasting

A raw international questionnaire is **not automatically model-ready**. Original forecasting requires 22 service-support, three context and eight priority features, harmonized under `questionbook/feature_manifest.csv` and `templates/FEATURE_HARMONIZATION_REVIEW.csv`. Provider definitions, currencies, amounts, units and applicable conditions must be validated locally; see `docs/HARMONIZATION_AND_MODELING.md`.

Only after harmonization, run `python run_toolkit.py --input /private/harmonized.csv --output /private/primary_01 --analysis primary` or `--analysis blocks`. For benchmarks, repeated splits, cross-domain and alternate-outcome runs, see `docs/INDEPENDENT_STUDY_ANALYSES.md` and `python run_advanced.py --help`. Models must be fitted and validated in the independent study. Predictive contributions are not causal.

## Supplementary research questions

Researchers can enable additional questions through `extensions_input/` without changing original scoring. The complete workflow generates an editable supplementary questionnaire, supplies the Excel `EXTENSION ENTRY` sheet and validates respondent-level joins during private export. See `docs/EXTENSIONS_AND_CONTRIBUTIONS.md` and run `python tools/build_extension_supplement.py --help`. Supplementary items are not inserted into the original 43-item survey or original 33-predictor set.

## Excel aggregate results

Python produces `RESULTS_VIEW_IMPORT.csv` with five aggregate columns. Use `python tools/prepare_results_view.py --input /private/results/RESULTS_VIEW_IMPORT.csv --output /private/view_01` to create a tab-separated file without headers. Paste **values** into `RESULTS VIEW!A4` after clearing placeholder A5. See `docs/EXCEL_AND_RESULTS_GUIDE.md`.

## Data privacy

This public-facing toolkit contains blank survey templates and 25 labeled synthetic examples, not observations from the original household survey. Keep completed surveys, respondent-level exports and private QA artifacts outside GitHub. See `DATA_PRIVACY.md` and `.gitignore` for safeguards.

## Reproducibility, rights and limitations

The original reproducibility archive of the study is separate and unchanged. Source, model configuration and executed code are versioned; the original 1,400-iteration CatBoost configuration remains intact. Synthetic modeling acceptance used a distinct 35-iteration smoke copy, so it demonstrates software functionality rather than external predictive validity. The Excel calculator opens and performs basic CORE-8 calculation in native Microsoft Excel. The user has additionally signed off the first/last research-entry rows and aggregate results viewer. Refer to `CITATION.cff`, `RIGHTS_AND_ATTRIBUTION.md`, `docs/SCOPE_AND_LIMITATIONS.md` and `docs/RELEASE_GATES.md`. The international toolkit is prepared as a separately licensed research-software release. The original-study reproducibility archive is **not** part of this repository and is reviewed separately.

## Technical-lock provenance and PDF export

This candidate's survey PDFs are exported from DOCX masters with font-only Word style/theme corrections (all questionnaire content unchanged), using Microsoft Word for Mac with verified Times New Roman PDF fonts. Private `executed_sources` now captures `src/wsqs/extensions.py`, `src/wsqs/provenance.py` and byte-identical enabled `--extensions` JSON specifications, with SHA-256 hashes in each independent-study run report. Registry snapshots contain specifications, never respondent answers. The original-study reproducibility archive remains separately frozen. This repository derives from the immutable 0.9.0-rc4 technical baseline. The original scoring, predictor specifications and questionnaires are unchanged.

## Citation

If you use the Water Service Quality Score (WSQS) measurement framework or the associated survey and analysis toolkit, please cite the accompanying preprint:

Mohanavelu, A., and Osman, K. K. (2026). *Operational Service Conditions are the primary predictors of Household Water Service Quality Across Heterogeneous Provision Systems*. Research Square [Preprint]. https://doi.org/10.21203/rs.3.rs-10888037/v1

Please also report the version of the WSQS toolkit used (v0.9.0 for this release). The root-level `CITATION.cff` supplies machine-readable citation metadata for GitHub. The preferred citation will be updated to the journal version when published.

## License and scholarly attribution

The toolkit's original software is provided under the **MIT License**
(`LICENSE`; © 2026 Aadhityaa Mohanavelu). Original WSQS questionnaires,
survey wording and supporting documentation are made available under
**Creative Commons Attribution 4.0 International (CC BY 4.0)**
(`LICENSE-CONTENT.md`). The Excel calculator combines MIT-licensed original
scoring formulas with CC BY 4.0 original survey/documentation content.
See `LICENSING.md` for a file-by-file scope explanation and exclusions.
Third-party material retains its own license; restricted household data and
the separately frozen original-study archive are not licensed here.

**Research credit:** Toolkit development by Aadhityaa Mohanavelu, with the
accompanying research coauthored by Aadhityaa Mohanavelu and Khalid K. Osman.
Cite the joint Research Square preprint
https://doi.org/10.21203/rs.3.rs-10888037/v1 and report the toolkit version
used. GitHub's root-level `CITATION.cff` provides the preferred citation.
