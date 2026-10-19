import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from wsqs.provenance import snapshot_extension_registry

class ProvenanceSnapshotTests(unittest.TestCase):
    def test_enabled_json_copied_exactly_and_hashed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "private_registry"
            src.mkdir()
            payload = b'{"enabled":true,"id":"EXT_EXAMPLE_A","question":"Test"}'
            (src / "a.json").write_bytes(payload)
            output = root / "executed_sources"
            checks = snapshot_extension_registry(src, output)
            self.assertEqual((output / "extension_registry/a.json").read_bytes(), payload)
            self.assertEqual(checks["extension_registry/a.json"], hashlib.sha256(payload).hexdigest())

    def test_disabled_spec_not_copied(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "specs"
            src.mkdir()
            (src / "disabled.json").write_text('{"enabled":false}')
            hashes = snapshot_extension_registry(src, root / "out")
            self.assertEqual(hashes, {})
            self.assertFalse((root / "out/extension_registry").exists())

    def test_symlink_spec_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "specs"
            src.mkdir()
            other = root / "outside.json"
            other.write_text('{"enabled":true}')
            (src / "unapproved.json").symlink_to(other)
            with self.assertRaises(ValueError):
                snapshot_extension_registry(src, root / "out")
