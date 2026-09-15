import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_usage_report import generate_report, validate_reports


class FakeData:
    messages = {'message_1': {'user_id': 'sample_user'},
                'message_2': {'user_id': 'evaluation_user'}}
    images = {'image_1': {'user_id': 'sample_user'}}
    tables = {'sample_requests': [{'user_id': 'sample_user'}],
              'requests': [{}, {}, {}]}

    @staticmethod
    def fingerprint():
        return {'requests.csv': 'fingerprint'}


def complete_report():
    return {
        'sample_only': False,
        'status': 'candidate_facts_ready',
        'input_sha256': FakeData.fingerprint(),
        'source_results': {'message_1': [], 'message_2': [], 'image_1': []},
        'blocked_sources': {},
        'usage_previous_runs': [],
        'usage_this_run': [{
            'model': 'gemini-3.5-flash-lite',
            'operation': 'generateContent',
            'time': '2026-09-13T01:00:00Z',
            'status': 'ok',
            'usage': {'promptTokenCount': 10, 'candidatesTokenCount': 5,
                      'totalTokenCount': 15},
        }],
        'cache_hits_previous_runs': 1,
        'cache_hits_this_run': 2,
    }


class GenerateUsageReportTests(unittest.TestCase):
    def test_validates_exact_dataset_fingerprint_and_source_inventory(self):
        report = complete_report()
        self.assertIs(report, validate_reports([report], FakeData(), expected_full_sources=3))
        for mutation in ('fingerprint', 'sources', 'source_count'):
            broken = complete_report()
            expected = 3
            if mutation == 'fingerprint':
                broken['input_sha256'] = {'requests.csv': 'stale'}
            elif mutation == 'sources':
                broken['source_results'].pop('image_1')
            else:
                expected = 231
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_reports([broken], FakeData(), expected_full_sources=expected)

    def test_incomplete_report_cannot_overwrite_existing_artifact(self):
        report = complete_report()
        report['status'] = 'quota_blocked'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'report.json'
            output = root / 'usage_report.md'
            source.write_text(json.dumps(report), encoding='utf-8')
            output.write_text('existing\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                generate_report([source], data=FakeData(), output=output)
            self.assertEqual('existing\n', output.read_text(encoding='utf-8'))

    def test_uses_actual_evaluation_request_count_and_writes_complete_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'report.json'
            output = root / 'evaluation' / 'usage_report.md'
            source.write_text(json.dumps(complete_report()), encoding='utf-8')
            summary = generate_report([source], data=FakeData(), output=output)
            self.assertEqual(3, summary['evaluation_requests'])
            self.assertEqual(3, summary['cache_hits'])
            rendered = output.read_text(encoding='utf-8')
            self.assertIn('Evaluation requests: 3', rendered)
            self.assertIn('gemini-3.5-flash-lite', rendered)


if __name__ == '__main__':
    unittest.main()
