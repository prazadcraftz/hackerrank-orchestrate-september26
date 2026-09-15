import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buy_or_wait.environment import load_credentials


class EnvironmentTests(unittest.TestCase):
    def test_load_only_allowed_names_without_overriding_environment(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'GEMINI_API_KEY': 'process-test'}, clear=True):
            path = Path(folder) / '.env'
            path.write_text('GEMINI_API_KEY=file-test\nGOOGLE_API_KEY="other-test"\nUNRELATED=ignored\n', encoding='utf-8')
            load_credentials(path)
            self.assertEqual('process-test', os.environ['GEMINI_API_KEY'])
            self.assertEqual('other-test', os.environ['GOOGLE_API_KEY'])
            self.assertNotIn('UNRELATED', os.environ)

    def test_placeholder_and_missing_file_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / '.env'
            load_credentials(path)
            path.write_text('GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE\n', encoding='utf-8')
            load_credentials(path)
            self.assertNotIn('GEMINI_API_KEY', os.environ)
