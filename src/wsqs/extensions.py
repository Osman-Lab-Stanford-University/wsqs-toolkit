"""Portable registry for opt-in supplementary WSQS questions.

Never changes original CORE8 scoring or the frozen 33 research predictors.
"""
from __future__ import annotations
import csv
import json
import math
import re
from pathlib import Path

IDENTIFIER = re.compile(r"EXT_[A-Z0-9_]{3,45}\Z")
KINDS = {"single_select", "number", "text"}
NEEDED = ("id", "question", "kind", "domain", "applicability", "source", "provenance", "contributor")


def read_registry(folder: Path, original_ids=(), predictor_ids=()):
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("Extension specification folder is missing")
    protected = set(original_ids) | set(predictor_ids)
    accepted = []
    json_files = sorted(folder.glob("*.json"))
    if len(json_files) > 31:
        raise ValueError("At most 31 supplementary Excel questions can be enabled")
    for filename in json_files:
        item = json.loads(filename.read_text(encoding="utf-8"))
        if not isinstance(item, dict):
            raise ValueError(f"Invalid extension document: {filename.name}")
        if not isinstance(item.get("enabled", False), bool):
            raise ValueError("Extension enabled flag must be a Boolean")
        if item.get("enabled") is False:
            continue
        for field in NEEDED:
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError("Incomplete extension metadata: " + field)
        qid = item["id"]
        if not IDENTIFIER.fullmatch(qid) or qid in protected:
            raise ValueError("Invalid or duplicate protected extension ID: " + qid)
        protected.add(qid)
        if item.get("scoring_policy") != "supplementary_only":
            raise ValueError("Extension cannot redefine original CORE-8")
        if item["kind"] not in KINDS:
            raise ValueError("Unsupported extension response type")
        if not isinstance(item.get("consent_review_required"), bool):
            raise ValueError("Consent review field must be Boolean")
        if item["kind"] == "single_select":
            opts = item.get("options")
            if (not isinstance(opts, list) or not 2 <= len(opts) <= 15
                    or not all(isinstance(opt, str) and opt.strip() for opt in opts)
                    or len(set(opts)) != len(opts)):
                raise ValueError("Invalid extension response options: " + qid)
        accepted.append(item)
    return accepted


def validate_value(spec, value):
    """Return canonical string for optional recorded answer or raise."""
    if value is None or str(value).strip() == "":
        return ""
    answer = str(value).strip()
    if answer[0] in "=+@" or "\r" in answer or "\n" in answer or "\t" in answer:
        raise ValueError("Formula-like or multiline extension response")
    if spec["kind"] == "single_select":
        if answer not in spec["options"]:
            raise ValueError("Unrecognized extension response for " + spec["id"])
    elif spec["kind"] == "number":
        try:
            number = float(answer)
        except ValueError as e:
            raise ValueError("Invalid numeric extension " + spec["id"]) from e
        if not math.isfinite(number):
            raise ValueError("Non-finite numeric extension " + spec["id"])
    else:
        if len(answer) > 3000:
            raise ValueError("Overlong supplementary text response")
    return answer
