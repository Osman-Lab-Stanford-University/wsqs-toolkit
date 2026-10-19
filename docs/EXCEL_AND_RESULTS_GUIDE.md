# Excel entry and aggregate results

The blank master workbook has nine sheets, including CORE8 QUESTIONS and an EXTENSION ENTRY sheet for optional researcher-defined items. It retains the original CORE-8 scoring and 33-feature scientific models. Use a private working copy for any respondent data.

Research entries use rows 5–104. The water-source-share status verifies all six percentages are entered, each is 0–100 and the sum is 100. A pasted invalid or negative percentage is flagged INVALID; a complete but non-100 total is CHECK SHARES. CORE-8 scores with 1–6 valid applicable domains remain calculated but are flagged LOW COVERAGE; Python also reports this category in aggregates and does not fit forecasting on those records.

The `CORE8 QUESTIONS` sheet contains all eight adapted question statements and the exact response alternatives. It is intended as a reference while using `MY WSQS`.

For supplementary questions, first generate an editable DOCX supplement with `python tools/build_extension_supplement.py --extensions /private/specs --output /private/supplement_01`; then enter matching record IDs and EXT_ headers on EXTENSION ENTRY. Export the completed working copy with `python tools/extract_research_entry.py --input /private/completed.xlsx --extensions /private/specs --output /private/respondents_01`. The export contains respondent-level data and must not be published.

For aggregate findings, use `python tools/prepare_results_view.py --input /private/model/RESULTS_VIEW_IMPORT.csv --output /private/view_01` and paste the no-header TSV values into RESULTS VIEW beginning in cell A4. Clear the original placeholder A5 first, preserve the five column headings on row 3.

**Native Microsoft Excel check remains required.** Open the blank master in Excel, confirm no recovery prompts, check MY WSQS and scoring on rows 5 and 104 and verify the pasted 246 synthetic aggregate findings through their final row. Python cannot certify native Excel recalculation.
