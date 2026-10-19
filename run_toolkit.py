"""WSQS independent-study scoring and analysis.

Produces aggregate results for Excel. This does not reproduce the
numerical results from the original household survey.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from wsqs.response_coding import coding
from wsqs.scoring import wsqs_from_severities
from wsqs.extensions import read_registry, validate_value
from wsqs.provenance import snapshot_extension_registry
from wsqs.models import (
    catboost_predictions,
    model_settings,
    prepare_catboost,
    summary_metrics,
)
from wsqs.extended import (
    block_columns,
    block_shapley,
    scientific_plans,
)

QIDS = (
    "Q2.2", "Q3.1", "Q4.1", "Q5.1",
    "Q6.1", "Q7.1", "Q8.1", "Q9.1",
)
DOMAINS = (
    "Affordability", "Access", "Reliability",
    "Efficiency", "Acceptability", "Quality",
    "Quantity", "Customer service",
)

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1048576), b""):
            h.update(part)
    return h.hexdigest()

def extensions_from(folder, protected):
    if folder is None:
        return []

    if not folder.is_dir():
        raise ValueError("Extension directory missing")

    accepted = []
    seen = set(protected)

    for path in sorted(folder.glob("*.json")):
        item = json.loads(path.read_text())

        if not item.get("enabled", False):
            continue

        identifier = item.get("id", "")

        if (
            not re.fullmatch(r"EXT_[A-Z0-9_]{3,45}", identifier)
            or identifier in seen
        ):
            raise ValueError("Invalid or duplicate extension ID")

        seen.add(identifier)

        if item.get("scoring_policy") != "supplementary_only":
            raise ValueError("Cannot redefine original CORE-8")

        for field in (
            "question", "kind", "domain", "source",
            "provenance", "contributor", "applicability"
        ):
            if not str(item.get(field, "")).strip():
                raise ValueError(
                    "Incomplete extension metadata: " + field
                )

        if item.get("kind") not in (
            "single_select", "number", "text"
        ):
            raise ValueError("Invalid extension response type")

        if not isinstance(
            item.get("consent_review_required"), bool
        ):
            raise ValueError("Consent review flag required")

        if item["kind"] == "single_select":
            options = item.get("options", [])
            if (
                len(options) < 2
                or len(options) > 15
                or len(set(options)) != len(options)
            ):
                raise ValueError("Invalid extension responses")

        accepted.append(item)

    return accepted

def score_core8(frame):
    response_map = coding()
    scores = []
    severities = []
    coverages = []

    for index, record in frame.iterrows():
        values = {}
        row_levels = []

        for qid in QIDS:
            answer = str(record[qid]).strip()

            if answer == "":
                severity = None
            else:
                key = (qid, answer)

                if key not in response_map:
                    raise ValueError(
                        f"Invalid response at row {index+2}: "
                        f"{qid} = {answer!r}"
                    )

                severity = response_map[key]

            values[qid] = severity
            row_levels.append(severity)

        observed = sum(v is not None for v in row_levels)
        coverages.append(observed)
        severities.append(row_levels)

        scores.append(
            wsqs_from_severities(values)
            if observed
            else np.nan
        )

    outcome = pd.DataFrame({
        "WSQS_100": scores,
        "domain_count": coverages,
    })

    domains = pd.DataFrame(
        severities,
        columns=DOMAINS,
        dtype=float
    )

    return outcome, domains

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--analysis",
        choices=("descriptive", "primary", "blocks"),
        default="descriptive"
    )
    parser.add_argument("--extensions", type=Path)
    parser.add_argument("--seed", type=int, default=20260714)
    args = parser.parse_args()

    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(source)

    if output.exists():
        raise FileExistsError("Existing results cannot be overwritten")

    if ROOT == output or ROOT in output.parents:
        raise ValueError("Private outputs must be outside source")

    with source.open(newline="", encoding="utf-8-sig") as stream:
        header = next(csv.reader(stream))

    if len(header) != len(set(header)):
        raise ValueError("Duplicate input column names")

    frame = pd.read_csv(
        source, dtype=object,
        keep_default_na=False,
        low_memory=False
    )

    if frame.empty:
        raise ValueError("Input data are empty")

    with (ROOT / "questionbook/feature_manifest.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        metadata = list(csv.DictReader(stream))

    features = [r["feature"] for r in metadata]

    if len(features) != 33 or len(set(features)) != 33:
        raise ValueError("Original feature manifest differs")

    with (ROOT / "spec/WSQS_Instrument_Schema.json").open(encoding="utf-8") as stream:
        original_ids = [item["Question_ID"] for item in json.load(stream)["questions"]]
    extensions = read_registry(args.extensions, original_ids, features) if args.extensions else []
    for item in extensions:
        if item["id"] in frame:
            for answer in frame[item["id"]]:
                validate_value(item, answer)

    outcome = None
    domain_levels = None

    if all(q in frame for q in QIDS):
        outcome, domain_levels = score_core8(frame)
        target = outcome["WSQS_100"]

    elif "WSQS_100" in frame:
        target = pd.to_numeric(
            frame["WSQS_100"], errors="coerce"
        )
        if not target.notna().all() or not target.between(0,100).all():
            raise ValueError("Invalid precomputed WSQS")

    else:
        raise ValueError(
            "Provide all eight CORE-8 response columns "
            "or an independently constructed WSQS_100"
        )

    if outcome is not None and "WSQS_100" in frame:
        supplied = pd.to_numeric(
            frame["WSQS_100"], errors="coerce"
        )

        if not np.isclose(
            supplied, target,
            atol=1e-5,
            rtol=0,
            equal_nan=True
        ).all():
            raise ValueError(
                "Provided score contradicts authoritative CORE-8 scoring"
            )

    aggregate = []

    def add(group, measure, value, n, notes=""):
        if pd.notna(value):
            aggregate.append({
                "analysis": group,
                "measure": measure,
                "value": float(value),
                "sample_size": int(n),
                "notes": notes
            })

    add("sample", "records", len(frame), len(frame))
    add("sample", "scored_records", target.notna().sum(), len(frame))
    if outcome is not None:
        counts = outcome["domain_count"]
        add("CORE8_coverage", "valid_eight_domains_n", (counts == 8).sum(), len(frame),
            "All eight applicable domain scores observed")
        add("CORE8_coverage", "valid_seven_domains_n", (counts == 7).sum(), len(frame),
            "Includes seven valid domains with eighth missing or structurally inapplicable")
        add("CORE8_coverage", "low_coverage_n", counts.between(1, 6).sum(), len(frame),
            "Scores remain computed but require LOW COVERAGE flag; do not interpret as full CORE-8")
        add("CORE8_coverage", "not_entered_n", (counts == 0).sum(), len(frame),
            "No valid applicable domain score")
        add("CORE8_coverage", "scored_at_least_seven_n", (counts >= 7).sum(), len(frame),
            "Recommended minimum coverage for comparative analysis")
        add("CORE8_coverage", "customer_service_structural_na_n", (
            frame["Q9.1"].astype(str).str.strip().eq(
                next(label for (qid,label),severity in coding().items()
                     if qid == "Q9.1" and severity is None)
            )
        ).sum(), len(frame), "Not equivalent to missing or poor Customer Service")
    add("CORE8", "mean", target.mean(), target.notna().sum())
    add("CORE8", "median", target.median(), target.notna().sum())

    if domain_levels is not None:
        for domain in DOMAINS:
            observed = domain_levels[domain].dropna()

            if len(observed):
                add(
                    "domain",
                    domain + "_mean_100",
                    25 * (5 - observed.mean()),
                    len(observed)
                )

            add(
                "domain",
                domain + "_observed_n",
                len(observed),
                len(frame)
            )

    for extension in extensions:
        name = extension["id"]

        if name in frame:
            values = frame[name].astype(str).str.strip()
            # Validate every entered extension response, including non-scored data.
            values = values.map(lambda value: validate_value(extension, value))

            add(
                "extension",
                name + "_observed_n",
                values.ne("").sum(),
                len(frame),
                "Supplementary only; excluded from CORE-8"
            )

    if args.analysis in ("primary", "blocks"):
        if len(frame) < 100 or target.isna().any():
            raise ValueError(
                "Modeling requires at least 100 valid scores"
            )
        if outcome is not None and (outcome["domain_count"] < 7).any():
            raise ValueError(
                "Forecasting requires at least seven valid applicable CORE-8 "
                "domains per record. Descriptive scores remain available "
                "and low coverage is reported separately."
            )

        missing = [c for c in features if c not in frame]

        if missing:
            raise ValueError(
                "Provide harmonized 33-feature data. Missing: "
                + ", ".join(missing)
            )

        numeric = [
            r["feature"] for r in metadata
            if r["type"] == "numeric"
        ]

        categorical = [
            f for f in features if f not in numeric
        ]

        X = frame[features].copy()

        for field in numeric:
            raw = X[field].astype(str).str.strip()
            values = pd.to_numeric(X[field], errors="coerce")

            if (raw.ne("") & values.isna()).any():
                raise ValueError(
                    "Invalid harmonized numeric feature: " + field
                )

            X[field] = values

        X = prepare_catboost(X, categorical, numeric)

        development, test = train_test_split(
            np.arange(len(frame)),
            test_size=.20,
            random_state=args.seed
        )

        fitting, validation = train_test_split(
            development,
            test_size=.20,
            random_state=args.seed
        )

        cfg = model_settings()
        cfg["catboost"]["random_seed"] = args.seed

        coalitions = {}

        if args.analysis == "blocks":
            coalitions[""] = summary_metrics(
                target.iloc[test],
                np.repeat(
                    target.iloc[development].mean(),
                    len(test)
                )
            )["r2"]

            groups = (
                "S", "C", "P",
                "SC", "SP", "CP", "SCP"
            )

        else:
            groups = ("SCP",)

        for group in groups:
            selected = (
                features
                if group == "SCP"
                else block_columns(group, scientific_plans())
            )

            cat = [
                f for f in categorical if f in selected
            ]

            print("Fitting:", group, flush=True)

            predictions, iterations = catboost_predictions(
                X[selected],
                target,
                cat,
                fitting,
                validation,
                test,
                np.sort(development),
                cfg
            )

            metrics = summary_metrics(
                target.iloc[test],
                predictions
            )

            for name, value in metrics.items():
                add(
                    args.analysis,
                    group + "." + name,
                    value,
                    len(test)
                )

            add(
                args.analysis,
                group + ".iterations",
                iterations,
                len(test)
            )

            coalitions[group] = metrics["r2"]

        if args.analysis == "blocks":
            contributions = block_shapley(coalitions)

            for block, value in contributions.items():
                add(
                    "shapley",
                    block + ".delta_r2",
                    value,
                    len(test),
                    "Predictive contribution, not causal"
                )

    output.mkdir(parents=True, exist_ok=False)

    cols = [
        "analysis", "measure", "value",
        "sample_size", "notes"
    ]

    with (output / "RESULTS_VIEW_IMPORT.csv").open(
        "x", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=cols)
        writer.writeheader()
        writer.writerows(aggregate)

    preserved = output / "executed_sources"
    preserved.mkdir()

    source_files = [
        "run_toolkit.py",
        "src/wsqs/scoring.py",
        "src/wsqs/response_coding.py",
        "src/wsqs/extensions.py",
        "src/wsqs/provenance.py",
        "src/wsqs/models.py",
        "src/wsqs/extended.py",
        "config/models.json",
        "config/scientific_plans.json",
        "questionbook/feature_manifest.csv",
        "questionbook/core8_response_coding.csv"
    ]

    for relative in source_files:
        origin = ROOT / relative
        destination = preserved / relative
        destination.parent.mkdir(
            parents=True, exist_ok=True
        )
        shutil.copyfile(origin, destination)

    extension_specification_hashes = snapshot_extension_registry(args.extensions, preserved)

    report = {
        "status": "INDEPENDENT_STUDY_ANALYSIS",
        "original_study_reproduction": False,
        "analysis": args.analysis,
        "records": len(frame),
        "aggregate_result_rows": len(aggregate),
        "input_sha256": sha(source),
        "seed": args.seed,
        "extensions": [e["id"] for e in extensions],
        "extension_specification_hashes": extension_specification_hashes,
        "household_predictions_exported": False,
        "source_hashes": {
            str(p.relative_to(preserved)): sha(p)
            for p in preserved.rglob("*")
            if p.is_file()
        }
    }

    (output / "RUN_REPORT.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )

    print(
        "PASS |", args.analysis,
        "| records:", len(frame),
        "| aggregate findings:", len(aggregate),
        flush=True
    )

if __name__ == "__main__":
    main()
