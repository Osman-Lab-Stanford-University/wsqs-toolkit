"""Privately export WSQS research inputs and registered supplementary questions.

Never export calculated Excel scoring cells. No observed respondent files belong
in the public software repository.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as E

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from wsqs.extensions import read_registry, validate_value

N = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
P = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CORE = {"Q2.2", "Q3.1", "Q4.1", "Q5.1", "Q6.1", "Q7.1", "Q8.1", "Q9.1"}


def safe_text(value):
    answer = str(value).strip()
    if not answer:
        return ""
    if answer[0] in "=+@" or (answer[0] == "-" and not re.fullmatch(r"-\d+(?:\.\d+)?", answer)):
        raise ValueError("Formula-like input in research worksheet")
    if any(ch in answer for ch in "\t\r\n"):
        raise ValueError("Multiline input in research worksheet")
    return answer


def letters_to_number(column):
    value = 0
    for character in column:
        value = value*26 + ord(character) - 64
    return value


def cell_value(cell, shared):
    if cell is None:
        return ""
    if cell.find(N+"f") is not None or cell.get("t") == "e":
        raise ValueError("Respondent-input cell contains a formula/error")
    if cell.get("t") == "inlineStr":
        return "".join(x.text or "" for x in cell.iter(N+"t"))
    val = cell.find(N+"v")
    if val is None:
        return ""
    if cell.get("t") == "s":
        return shared[int(val.text)]
    return val.text or ""


def workbook_sheets(archive):
    book = E.fromstring(archive.read("xl/workbook.xml"))
    rels = E.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    links = {rel.get("Id"): rel.get("Target") for rel in rels.findall(P+"Relationship")}
    result = {}
    for sheet in book.findall(N+"sheets/"+N+"sheet"):
        dest = links.get(sheet.get(R+"id"))
        if not dest:
            raise ValueError("Missing Excel sheet relationship")
        dest = dest.replace("\\", "/")
        if dest.startswith("/"):
            member = dest.lstrip("/")
        elif dest.startswith("xl/"):
            member = dest
        else:
            member = "xl/" + dest
        if ".." in Path(member).parts or member not in archive.namelist():
            raise ValueError("Invalid worksheet target")
        result[sheet.get("name")] = E.fromstring(archive.read(member))
    return result


def sheet_rows(root):
    return {int(row.get("r")): row for row in root.findall(N+"sheetData/"+N+"row")}


def row_cells(rows, number):
    row = rows.get(number)
    if row is None:
        return {}
    return {re.match(r"([A-Z]+)", cell.get("r")).group(1): cell
            for cell in row.findall(N+"c")}


def heading_columns(rows, shared):
    titles = [(letters_to_number(col), col, cell_value(cell, shared).strip())
              for col, cell in row_cells(rows, 4).items()]
    return sorted(titles)


def extract(path, extensions_dir=None):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Damaged Excel workbook")
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            ss = E.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(N+"t"))
                      for si in ss.findall(N+"si")]
        sheets = workbook_sheets(archive)
    if "RESEARCH ENTRY" not in sheets:
        raise ValueError("Missing WSQS RESEARCH ENTRY sheet")
    rows = sheet_rows(sheets["RESEARCH ENTRY"])
    headers = heading_columns(rows, shared)
    titles = [x[2] for x in headers]
    if not titles or titles[0] != "Record ID" or "SCORE_Q2.2" not in titles:
        raise ValueError("Research workbook headings differ")
    fields = headers[:titles.index("SCORE_Q2.2")]
    keys = [x[2] for x in fields]
    if len(keys)!=len(set(keys)) or not CORE.issubset(keys):
        raise ValueError("Duplicate or missing original CORE-8 columns")
    data = []
    identifiers = set()
    for number in range(5, 105):
        cells = row_cells(rows, number)
        record = {label: safe_text(cell_value(cells.get(col), shared))
                  for _,col,label in fields}
        if not any(record.values()):
            continue
        record_id = record["Record ID"]
        if not record_id or record_id in identifiers:
            raise ValueError("Duplicate or missing Record ID")
        identifiers.add(record_id)
        data.append(record)
    if not data:
        raise ValueError("No entered research respondents")

    # Sheet is optional. If populated, an explicit approved registry is mandatory.
    extension_fields=[]
    extension_data={}
    if "EXTENSION ENTRY" in sheets:
        erows = sheet_rows(sheets["EXTENSION ENTRY"])
        extension_headers = heading_columns(erows, shared)
        optional = [(col, label) for _,col,label in extension_headers if label and label != "Record ID"]
        if len({label for _,label in optional})!=len(optional):
            raise ValueError("Duplicate extension IDs on the Excel sheet")
        used = False
        for number in range(5, 105):
            cells = row_cells(erows, number)
            if any(cell_value(cell, shared).strip() for cell in cells.values()):
                used=True
                break
        if used or optional:
            if extensions_dir is None:
                raise ValueError("Supplementary sheet contains data or headers: pass --extensions for explicit validated export")
            schema=json.loads((ROOT/"spec/WSQS_Instrument_Schema.json").read_text(encoding="utf-8"))
            original_ids={item["Question_ID"] for item in schema["questions"]}
            manifest=list(csv.DictReader((ROOT/"questionbook/feature_manifest.csv").open(newline="")))
            specs=read_registry(extensions_dir, original_ids, {m["feature"] for m in manifest})
            registry={spec["id"]:spec for spec in specs}
            unknown=[label for _,label in optional if label not in registry]
            if unknown:
                raise ValueError("Unregistered Excel extension header(s): "+", ".join(unknown))
            absent=[k for k in registry if k not in {label for _,label in optional}]
            if absent:
                raise ValueError("Enabled registered extension missing Excel header(s): "+", ".join(absent))
            extension_fields=[label for _,label in optional]
            extension_ids=set()
            for number in range(5, 105):
                cells=row_cells(erows, number)
                identifier=safe_text(cell_value(cells.get("A"),shared))
                values={label:validate_value(registry[label],cell_value(cells.get(col),shared))
                        for col,label in optional}
                if not identifier and any(values.values()):
                    raise ValueError("Supplementary response without Record ID")
                if not identifier:
                    continue
                if identifier not in identifiers or identifier in extension_ids:
                    raise ValueError("Unmatched or duplicate supplementary Record ID")
                extension_ids.add(identifier)
                extension_data[identifier]=values

    for record in data:
        record.update(extension_data.get(record["Record ID"], {label:"" for label in extension_fields}))
    return keys+extension_fields, data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--extensions",type=Path,
                        help="Folder of approved enabled EXT_ JSON question specifications")
    args=parser.parse_args()
    inp=args.input.expanduser().resolve()
    out=args.output.expanduser().resolve()
    if not inp.is_file() or out.exists() or out==ROOT or ROOT in out.parents:
        raise ValueError("Use an existing PRIVATE workbook and a new PRIVATE output directory outside the toolkit")
    names, records=extract(inp,args.extensions)
    out.mkdir(parents=True,exist_ok=False)
    with (out/"PRIVATE_RESEARCH_RESPONSES.csv").open("x",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=names)
        writer.writeheader();writer.writerows(records)
    (out/"EXPORT_REPORT.json").write_text(json.dumps({
        "records":len(records),"supplementary_fields":[x for x in names if x.startswith('EXT_')],
        "contains_respondent_data":True,"publication_authorized":False,
        "harmonized_33_predictors":False
    },indent=2)+"\n")
    print(f"PASS | Exported {len(records)} PRIVATE records with {len([x for x in names if x.startswith('EXT_')])} supplementary fields. DO NOT PUBLISH.")


if __name__ == "__main__":
    main()
