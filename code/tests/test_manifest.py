import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from buy_or_wait.contracts import ContractError
from buy_or_wait.manifest import bundle_evidence_manifest


def fake_data():
    return SimpleNamespace(
        messages={'message_1': {}}, images={'image_1': {}},
        fingerprint=lambda: {'requests.csv': 'hash'},
    )


def report():
    return {
        'sample_only': False, 'status': 'candidate_facts_ready',
        'input_sha256': {'requests.csv': 'hash'},
        'source_results': {'message_1': [], 'image_1': []},
        'blocked_sources': {},
    }


class ManifestTests(unittest.TestCase):
    def test_bundles_complete_report_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, destination = root / 'report.json', root / 'code' / 'evidence_manifest.json'
            source.write_text(json.dumps(report()), encoding='utf-8')
            bundled = bundle_evidence_manifest(fake_data(), source, destination)
            self.assertEqual(report(), bundled)
            self.assertEqual(report(), json.loads(destination.read_text(encoding='utf-8')))
            self.assertFalse(destination.with_suffix('.json.tmp').exists())

    def test_rejects_partial_inventory_without_overwriting_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, destination = root / 'report.json', root / 'evidence_manifest.json'
            broken = report()
            broken['source_results'].pop('image_1')
            source.write_text(json.dumps(broken), encoding='utf-8')
            destination.write_text('existing', encoding='utf-8')
            with self.assertRaisesRegex(ContractError, 'exact source inventory'):
                bundle_evidence_manifest(fake_data(), source, destination)
            self.assertEqual('existing', destination.read_text(encoding='utf-8'))

    def test_rejects_sample_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'report.json'
            sample = report()
            sample['sample_only'] = True
            source.write_text(json.dumps(sample), encoding='utf-8')
            with self.assertRaisesRegex(ContractError, 'full-dataset'):
                bundle_evidence_manifest(fake_data(), source, root / 'manifest.json')


if __name__ == '__main__':
    unittest.main()
