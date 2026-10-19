# Independent-study WSQS analyses

The original-study reproduction package is separate and remains frozen.

## First, check your international survey

Run:

    python survey_readiness.py --input /private/survey.csv --output /private/readiness_01

This reports input completeness, CORE-8 response validity and water-source
percentage consistency. It does not export household observations.

## Before forecasting

Provide all 33 original predictor columns listed in
`questionbook/feature_manifest.csv`, using explicitly documented local
harmonization.

International currency amounts, water volumes, provider categories
and provision-applicability rules must not silently inherit historical
India-specific categorical encodings.

The advanced analysis CSV must also contain the original eight CORE-8
question-response labels.

## Available analyses

    python run_advanced.py --input /private/model_ready.csv --output /private/benchmark_01 --mode benchmark
    python run_advanced.py --input /private/model_ready.csv --output /private/repeated_01 --mode repeated --splits 10
    python run_advanced.py --input /private/model_ready.csv --output /private/domain_01 --mode cross-domain
    python run_advanced.py --input /private/model_ready.csv --output /private/outcomes_01 --mode outcomes

For an enabled supplementary predictor extension:

    python run_advanced.py --input /private/with_extension.csv --output /private/extension_01 --mode extension-model --extensions /private/extension_specs

Each output directory must be new and outside the public repository.

Python exports `RESULTS_VIEW_IMPORT.csv`. Open it in Excel or paste its
five data columns into the workbook's RESULTS VIEW sheet, starting at A4
without repeating the header row.

These analyses produce results for the new study, not the published
Tamil Nadu numerical results. They are predictive, not causal.
An international adaptation requires local validation.
