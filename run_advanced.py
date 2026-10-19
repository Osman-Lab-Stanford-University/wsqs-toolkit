"""Advanced WSQS analyses for independently collected, harmonized data.

Does not reproduce historical Tamil Nadu results.
Exports aggregate scientific evaluations only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import shutil
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from wsqs.response_coding import coding
from wsqs.extensions import read_registry, validate_value
from wsqs.provenance import snapshot_extension_registry
from wsqs.models import (
    model_settings, prepare_catboost, prepare_sklearn,
    catboost_predictions, other_predictions,
    summary_metrics, LEARNERS
)
from wsqs.extended import block_columns, scientific_plans

QIDS = [
    "Q2.2", "Q3.1", "Q4.1", "Q5.1",
    "Q6.1", "Q7.1", "Q8.1", "Q9.1"
]

DOMAINS = [
    "Affordability", "Access", "Reliability",
    "Efficiency", "Acceptability", "Quality",
    "Quantity", "Customer_service"
]

FIELDS = [
    "analysis", "measure", "value", "sample_size", "notes"
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1048576), b""):
            h.update(part)
    return h.hexdigest()


def partition(n, seed):
    require(n >= 100, "Modeling requires at least 100 records")

    development, test = train_test_split(
        np.arange(n), test_size=.20, random_state=seed
    )

    fit, validation = train_test_split(
        development, test_size=.20, random_state=seed
    )

    assert not set(fit) & set(validation)
    assert not set(development) & set(test)

    return fit, validation, test, np.sort(development)


def load_data(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        header = next(csv.reader(stream))

    require(
        len(header) == len(set(header)),
        "Duplicate CSV column headings"
    )

    frame = pd.read_csv(
        path, dtype=object,
        keep_default_na=False,
        low_memory=False
    )

    require(len(frame) > 0, "Empty dataset")
    require(
        all(q in frame for q in QIDS),
        "All eight CORE-8 response columns are required"
    )

    reference = coding()
    values = []

    for index, record in frame.iterrows():
        severity = []

        for question in QIDS:
            answer = str(record[question]).strip()

            if not answer:
                severity.append(np.nan)
                continue

            require(
                (question, answer) in reference,
                f"Invalid CORE-8 answer in record {index+1}: {question}"
            )

            value = reference[(question, answer)]
            severity.append(
                float(value) if value is not None else np.nan
            )

        values.append(severity)

    severity = pd.DataFrame(
        values, columns=DOMAINS, dtype=float
    )

    coverage = severity.notna().sum(axis=1)

    require(
        coverage.ge(7).all(),
        "Advanced modeling requires at least seven "
        "applicable CORE-8 domains per record"
    )

    outcome = 25 * (5 - severity.mean(axis=1))

    if "WSQS_100" in frame:
        supplied = pd.to_numeric(
            frame["WSQS_100"], errors="coerce"
        )

        require(
            np.allclose(supplied, outcome, rtol=0, atol=1e-5),
            "Supplied WSQS differs from authoritative CORE-8"
        )

    return frame, severity, outcome


def load_features(frame):
    with (ROOT / "questionbook/feature_manifest.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        manifest = list(csv.DictReader(stream))

    features = [item["feature"] for item in manifest]

    require(
        len(features) == 33 and len(set(features)) == 33,
        "Original 33-feature manifest differs"
    )

    missing = [name for name in features if name not in frame]

    require(
        not missing,
        "Harmonized model columns missing: " + ", ".join(missing)
    )

    numeric = [
        item["feature"] for item in manifest
        if item["type"] == "numeric"
    ]

    categorical = [
        feature for feature in features
        if feature not in numeric
    ]

    X = frame[features].copy()

    for name in numeric:
        text = X[name].astype(str).str.strip()
        number = pd.to_numeric(text, errors="coerce")

        require(
            not (text.ne("") & number.isna()).any(),
            "Unrecognized numeric predictor: " + name
        )

        X[name] = number

    for name in categorical:
        X[name] = (
            X[name].astype("string").replace("", pd.NA)
        )

    return X, categorical, numeric, features


def extensions(folder, protected, frame):
    if folder is None:
        return []
    accepted = read_registry(folder, protected)
    for item in accepted:
        name = item["id"]
        require(name in frame, "Active extension missing from input: " + name)
        for value in frame[name]:
            validate_value(item, value)
    return accepted


def fit_catboost(X, y, categorical, split, seed):
    fit, validation, test, development = split

    numeric = [
        name for name in X if name not in categorical
    ]

    prepared = prepare_catboost(
        X, categorical, numeric
    )

    config = model_settings()
    config["catboost"]["random_seed"] = seed

    predictions, iterations = catboost_predictions(
        prepared, y, categorical,
        fit, validation, test, development, config
    )

    return {
        **summary_metrics(y.iloc[test], predictions),
        "iterations": iterations,
        "heldout_n": len(test)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--input", type=Path, required=True
    )
    parser.add_argument(
        "--output", type=Path, required=True
    )
    parser.add_argument(
        "--mode", required=True,
        choices=[
            "benchmark", "repeated", "cross-domain",
            "outcomes", "extension-model"
        ]
    )
    parser.add_argument(
        "--seed", type=int, default=20260714
    )
    parser.add_argument(
        "--splits", type=int, default=3
    )
    parser.add_argument(
        "--extensions", type=Path
    )

    args = parser.parse_args()

    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()

    require(source.is_file(), "Input CSV missing")
    require(not output.exists(), "Output directory already exists")
    require(
        ROOT != output and ROOT not in output.parents,
        "Private results must be outside the public source directory"
    )

    frame, severity, target = load_data(source)
    X, categorical, numeric, features = load_features(frame)

    with (ROOT / "spec/WSQS_Instrument_Schema.json").open(encoding="utf-8") as stream:
        original_ids = [item["Question_ID"] for item in json.load(stream)["questions"]]
    extra = read_registry(args.extensions, original_ids, features) if args.extensions else []
    for item in extra:
        name = item["id"]
        require(name in frame, "Active extension missing from input data: " + name)
        frame[name].astype(str).map(lambda value: validate_value(item, value))

    findings = []
    fitted = 0

    def emit(category, name, value, count, note=""):
        if value is None:
            return

        value = float(value)

        if np.isfinite(value):
            findings.append({
                "analysis": category,
                "measure": name,
                "value": value,
                "sample_size": int(count),
                "notes": note
            })

    def emit_model(category, label, result, n):
        for metric, value in result.items():
            if metric != "heldout_n":
                emit(
                    category,
                    label + "." + metric,
                    value, n,
                    "Independent-study predictive evaluation"
                )

    def cat_model(
        group, seed, y=None, cols=None,
        predictors=None, cat=None, split=None
    ):
        nonlocal fitted

        split = (
            partition(len(target), seed)
            if split is None else split
        )

        predictors = X if predictors is None else predictors
        categories = categorical if cat is None else cat

        cols = (
            block_columns(group, scientific_plans())
            if cols is None else cols
        )

        selected_categories = [
            name for name in categories if name in cols
        ]

        result = fit_catboost(
            predictors[cols],
            target if y is None else y,
            selected_categories,
            split, seed
        )

        fitted += 1
        return result

    if args.mode == "benchmark":
        split = partition(len(target), args.seed)

        settings = model_settings()
        settings["catboost"]["random_seed"] = args.seed

        for learner in LEARNERS:
            if learner == "CatBoost":
                result = cat_model(
                    "SCP", args.seed, split=split
                )

            else:
                prepared = prepare_sklearn(
                    X, categorical, numeric
                )

                prediction, alpha = other_predictions(
                    learner, prepared, target,
                    categorical, numeric,
                    args.seed, *split, settings
                )

                result = summary_metrics(
                    target.iloc[split[2]], prediction
                )

                if np.isfinite(float(alpha)):
                    result["alpha"] = alpha

                if learner != "Mean baseline":
                    fitted += 1

            emit_model(
                "benchmark", learner,
                result, len(split[2])
            )

            print("PASS | Benchmark:", learner, flush=True)

    elif args.mode == "repeated":
        require(
            2 <= args.splits <= 10,
            "Repeated splits must be between 2 and 10"
        )

        for repeat in range(args.splits):
            seed = args.seed + repeat
            result = cat_model("SCP", seed)

            emit_model(
                "repeated", f"seed_{seed}",
                result, result["heldout_n"]
            )

            print(
                "PASS | Repeated split:", seed,
                flush=True
            )

        rmses = [
            row["value"] for row in findings
            if row["measure"].endswith(".rmse_100")
        ]

        r2s = [
            row["value"] for row in findings
            if row["measure"].endswith(".r2")
        ]

        emit(
            "repeated_summary",
            "mean_rmse_100",
            np.mean(rmses),
            len(target)
        )

        emit(
            "repeated_summary",
            "mean_r2",
            np.mean(r2s),
            len(target)
        )

    elif args.mode == "cross-domain":
        split = partition(len(target), args.seed)
        fit, validation, test, _ = split

        plans = scientific_plans()

        for domain in DOMAINS:
            domain_y = 25 * (5 - severity[domain])
            observed = domain_y.notna()

            domain_fit = np.array([
                i for i in fit if observed.iloc[i]
            ])

            domain_validation = np.array([
                i for i in validation if observed.iloc[i]
            ])

            domain_test = np.array([
                i for i in test if observed.iloc[i]
            ])

            require(
                min(
                    len(domain_fit),
                    len(domain_validation),
                    len(domain_test)
                ) >= 5,
                "Insufficient respondents for " + domain
            )

            domain_split = (
                domain_fit,
                domain_validation,
                domain_test,
                np.sort(
                    np.concatenate((
                        domain_fit, domain_validation
                    ))
                )
            )

            result = cat_model(
                "SCP", args.seed,
                y=domain_y,
                cols=plans["cross_domain"][domain],
                split=domain_split
            )

            emit_model(
                "cross_domain", domain,
                result, len(domain_test)
            )

            print(
                "PASS | Cross-domain:", domain,
                flush=True
            )

    elif args.mode == "outcomes":
        split = partition(len(target), args.seed)
        development = split[3]

        seven_acceptability = (
            severity.drop(columns="Acceptability")
        )

        seven_customer_service = (
            severity.drop(columns="Customer_service")
        )

        core7a = 25 * (
            5 - seven_acceptability.mean(axis=1)
        )

        core7b = 25 * (
            5 - seven_customer_service.mean(axis=1)
        )

        priority_fields = [
            f"{domain}_priority_0_10"
            for domain in DOMAINS
        ]

        priorities = X[priority_fields].apply(
            pd.to_numeric, errors="coerce"
        )

        require(
            priorities.notna().all().all()
            and priorities.stack().between(0, 10).all()
            and (priorities.stack() % 1 == 0).all(),
            "Alternative outcomes require eight valid "
            "integer priority ratings"
        )

        priorities.columns = DOMAINS

        weights = priorities.iloc[development].mean()
        require(
            weights.sum() > 0,
            "Invalid population weights"
        )

        weights = weights / weights.sum()

        available = severity.notna()

        population_denominator = (
            available.mul(weights, axis=1).sum(axis=1)
        )

        population = 25 * (
            5 - severity.mul(
                weights, axis=1
            ).sum(axis=1).div(population_denominator)
        )

        individual_weights = priorities.where(available)
        individual_denominator = individual_weights.sum(axis=1)

        individualized = (
            severity.mul(individual_weights)
            .sum(axis=1)
            .div(individual_denominator.where(
                individual_denominator > 0
            ))
        )

        individualized = individualized.where(
            individual_denominator > 0,
            severity.mean(axis=1)
        )

        individual = 25 * (5 - individualized)

        alternatives = [
            ("CORE7A", core7a),
            ("CORE7B", core7b),
            ("POPULATION_PRIORITY", population),
            ("INDIVIDUAL_PRIORITY", individual)
        ]

        for name, alternative in alternatives:
            require(
                alternative.notna().all()
                and alternative.between(0, 100).all(),
                "Invalid alternative outcome: " + name
            )

            result = cat_model(
                "SC", args.seed,
                y=alternative,
                split=split
            )

            emit_model(
                "outcome_sensitivity",
                name, result, len(split[2])
            )

            print(
                "PASS | Outcome:", name,
                flush=True
            )

        emit(
            "outcome_sensitivity",
            "zero_priority_fallback_n",
            (individual_denominator <= 0).sum(),
            len(target)
        )

    elif args.mode == "extension-model":
        supported = [
            item for item in extra
            if item["kind"] in (
                "single_select", "number"
            )
        ]

        require(
            len(supported) > 0,
            "No enabled model-compatible extensions"
        )

        split = partition(len(target), args.seed)

        baseline = cat_model(
            "SCP", args.seed, split=split
        )

        emit_model(
            "extension_baseline",
            "SCP", baseline, len(split[2])
        )

        expanded = X.copy()
        categories = categorical.copy()

        for item in supported:
            name = item["id"]
            values = frame[name].astype(str).str.strip()

            if item["kind"] == "single_select":
                expanded[name] = values.where(
                    values.ne(""), "__UNANSWERED__"
                )
                categories.append(name)

            else:
                expanded[name] = pd.to_numeric(
                    values, errors="coerce"
                )

        result = cat_model(
            "SCP", args.seed,
            cols=list(expanded),
            predictors=expanded,
            cat=categories,
            split=split
        )

        emit_model(
            "extension_model",
            "SCP_plus_extensions",
            result, len(split[2])
        )

        print(
            "PASS | Supplementary extension model",
            flush=True
        )

    require(findings, "No aggregate findings generated")

    output.mkdir(parents=True, exist_ok=False)

    with (output / "RESULTS_VIEW_IMPORT.csv").open(
        "x", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=FIELDS
        )
        writer.writeheader()
        writer.writerows(findings)

    source_dir = output / "executed_sources"
    source_dir.mkdir()

    protected = [
        "run_advanced.py",
        "src/wsqs/models.py",
        "src/wsqs/extended.py",
        "src/wsqs/response_coding.py",
        "src/wsqs/extensions.py",
        "src/wsqs/provenance.py",
        "src/wsqs/scoring.py",
        "questionbook/feature_manifest.csv",
        "config/models.json",
        "config/scientific_plans.json"
    ]

    for relative in protected:
        src = ROOT / relative
        dest = source_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)

    extension_specification_hashes = snapshot_extension_registry(args.extensions, source_dir)

    report = {
        "status": "INDEPENDENT_STUDY_AGGREGATES",
        "mode": args.mode,
        "record_count": len(frame),
        "seed": args.seed,
        "fitted_models": fitted,
        "results_rows": len(findings),
        "input_sha256": sha256(source),
        "extensions": [item["id"] for item in extra],
        "extension_specification_hashes": extension_specification_hashes,
        "original_study_reproduction": False,
        "household_predictions_exported": False,
        "execution_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "environment": {
            "python": platform.python_version(),
            **{
                name: metadata.version(name)
                for name in (
                    "numpy", "pandas", "scipy",
                    "scikit-learn", "catboost"
                )
            }
        },
        "source_checksums": {
            str(path.relative_to(source_dir)): sha256(path)
            for path in source_dir.rglob("*")
            if path.is_file()
        }
    }

    (output / "RUN_REPORT.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )

    (output / "EXECUTION_LOG.txt").write_text(
        "Independent WSQS analysis\n"
        + json.dumps(report, indent=2) + "\n"
    )

    print(
        "PASS |", args.mode,
        "| models fitted:", fitted,
        "| aggregate results:", len(findings),
        flush=True
    )


if __name__ == "__main__":
    main()
