"""Aggregate-only readiness review of an international WSQS survey."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from wsqs.response_coding import coding

CORE = [
    "Q2.2", "Q3.1", "Q4.1", "Q5.1",
    "Q6.1", "Q7.1", "Q8.1", "Q9.1"
]

SHARES = [
    f"Q1.2_{name}_pct"
    for name in (
        "public", "groundwater", "surface",
        "tanker", "packaged", "other"
    )
]

MULTI = {
    "Q1.2": SHARES,
    "Q2.3": [
        "Q2.3_amount", "Q2.3_currency", "Q2.3_status"
    ],
    "Q8.2": [
        "Q8.2_volume", "Q8.2_unit", "Q8.2_status"
    ],
    "Q15.17": [
        "Q15.17_amount", "Q15.17_currency",
        "Q15.17_status"
    ]
}


def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(source)

    if output.exists():
        raise FileExistsError(
            "Readiness output already exists"
        )

    if ROOT == output or ROOT in output.parents:
        raise ValueError(
            "Private results must be outside source directory"
        )

    with source.open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        headers = next(csv.reader(stream))

    if len(headers) != len(set(headers)):
        raise ValueError("Duplicate survey columns")

    data = pd.read_csv(
        source, dtype=object,
        keep_default_na=False,
        low_memory=False
    )

    if len(data) == 0:
        raise ValueError("Empty survey dataset")

    schema = json.loads(
        (
            ROOT / "spec/WSQS_Instrument_Schema.json"
        ).read_text()
    )

    reference = coding()

    missing_core = [
        q for q in CORE if q not in data
    ]

    if missing_core:
        raise ValueError(
            "Missing CORE-8 items: " + ", ".join(missing_core)
        )

    invalid = {}
    coverage = []

    for question in CORE:
        values = data[question].astype(str).str.strip()

        invalid[question] = int(
            (~values.map(
                lambda x: x == ""
                or (question, x) in reference
            )).sum()
        )

    for _, record in data.iterrows():
        number = 0

        for question in CORE:
            answer = str(record[question]).strip()

            if (
                (question, answer) in reference
                and reference[(question, answer)] is not None
            ):
                number += 1

        coverage.append(number)

    available = []
    missing = []

    for item in schema["questions"]:
        identifier = item["Question_ID"]
        fields = MULTI.get(identifier, [identifier])

        if all(field in data for field in fields):
            available.append(identifier)
        else:
            missing.append(identifier)

    shares = {
        "not_provided": len(data),
        "valid": 0,
        "invalid_or_incomplete": 0
    }

    if all(name in data for name in SHARES):
        source_shares = data[SHARES]

        numbers = source_shares.apply(
            lambda column: pd.to_numeric(
                column, errors="coerce"
            )
        )

        entered = source_shares.astype(str).apply(
            lambda column: column.str.strip().ne("")
        ).any(axis=1)

        valid = (
            entered
            & numbers.notna().all(axis=1)
            & numbers.ge(0).all(axis=1)
            & numbers.le(100).all(axis=1)
            & (
                numbers.sum(axis=1) - 100
            ).abs().lt(1e-6)
        )

        shares = {
            "not_provided": int((~entered).sum()),
            "valid": int(valid.sum()),
            "invalid_or_incomplete": int(
                (entered & ~valid).sum()
            )
        }

    report = {
        "status": "SURVEY_READINESS_REVIEW_ONLY",
        "publication_authorized": False,
        "records": len(data),
        "core8_invalid_response_counts": invalid,
        "core8_at_least_seven_applicable_n": sum(
            count >= 7 for count in coverage
        ),
        "core8_low_coverage_n": sum(
            count < 7 for count in coverage
        ),
        "question_ids_present": len(available),
        "question_ids_missing": missing,
        "water_source_shares": shares,
        "automatically_model_ready": False,
        "local_harmonization_required": True,
        "international_validation_established": False,
        "input_sha256": checksum(source),
        "household_rows_exported": False
    }

    output.mkdir(parents=True, exist_ok=False)

    (output / "SURVEY_READINESS.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )

    print(
        "PASS | Survey readiness reviewed:",
        len(data), "records"
    )
    print(
        "PASS | Only aggregate readiness information exported"
    )


if __name__ == "__main__":
    main()
