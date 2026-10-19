"""Private source provenance for optional researcher extensions.

Enabled JSON registry specifications are copied byte-for-byte into the
researcher's PRIVATE executed_sources directory. No respondent data.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

def snapshot_extension_registry(folder, executed_sources):
    if folder is None:
        return {}
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Extension registry must be a real directory")
    dest = Path(executed_sources) / "extension_registry"
    hashes = {}
    for src in sorted(folder.glob("*.json")):
        if src.is_symlink() or not src.is_file():
            raise ValueError("Unsafe extension registry specification")
        payload = src.read_bytes()
        spec = json.loads(payload)
        if not isinstance(spec, dict):
            raise ValueError("Extension specification must be a JSON object")
        if spec.get("enabled") is not True:
            continue
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / src.name
        target.write_bytes(payload)
        hashes["extension_registry/" + src.name] = hashlib.sha256(payload).hexdigest()
    return hashes
