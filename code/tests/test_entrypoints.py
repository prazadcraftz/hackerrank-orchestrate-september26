import importlib.util
import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_ROOT = REPO_ROOT / 'code'
sys.path.insert(0, str(CODE_ROOT))


def run_script(*arguments):
    return subprocess.run(
        [sys.executable, *map(str, arguments)], cwd=REPO_ROOT,
        capture_output=True, text=True, encoding='utf-8', timeout=30,
    )


class EntrypointTests(unittest.TestCase):
    def test_main_help_is_terminal_runnable(self):
        result = run_script(CODE_ROOT / 'main.py', '--help')
        self.assertEqual(0, result.returncode, result.stderr)
        for command in ('audit', 'bundle-evidence', 'cache-audit', 'consolidate-cache',
                        'evaluate', 'extract', 'predict'):
            self.assertIn(command, result.stdout)

    def test_audit_accepts_explicit_dataset_from_repo_root(self):
        result = run_script(CODE_ROOT / 'main.py', '--dataset', REPO_ROOT / 'dataset', 'audit')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('"errors": []', result.stdout)
        self.assertIn('"requests": 250', result.stdout)

    def test_evaluator_wrapper_accepts_dataset_option(self):
        result = run_script(CODE_ROOT / 'evaluation' / 'main.py', '--help')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('--dataset', result.stdout)
        self.assertIn('predictions', result.stdout)

    def test_usage_and_packaging_entrypoints_have_help(self):
        for script in ('generate_usage_report.py', 'package_submission.py'):
            with self.subTest(script=script):
                result = run_script(CODE_ROOT / script, '--help')
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn('usage:', result.stdout)

    def test_zero_arguments_run_latest_with_bundled_manifest_and_root_output(self):
        spec = importlib.util.spec_from_file_location('buy_or_wait_cli', CODE_ROOT / 'main.py')
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        data = object()
        result = {'status': 'validated', 'rows_completed': 250, 'blocked': {}}
        with patch.object(cli, 'Dataset', return_value=data), \
             patch.object(cli, 'load_report', return_value={'report': True}) as load, \
             patch.object(cli, 'resolve_candidates', return_value={'issues': []}), \
             patch.object(cli, 'run_predictions', return_value=result) as run, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(0, cli.main([]))
        self.assertEqual(CODE_ROOT / 'evidence_manifest.json', load.call_args.args[0])
        self.assertEqual(REPO_ROOT / 'output.csv', run.call_args.args[2])
        self.assertEqual(CODE_ROOT / 'runs' / 'final-trace.json', run.call_args.args[3])
        self.assertEqual('latest', run.call_args.kwargs['expense_policy'])


if __name__ == '__main__':
    unittest.main()
