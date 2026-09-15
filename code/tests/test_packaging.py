import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from buy_or_wait.packaging import FIXED_TIMESTAMP, PackagingError, build_code_zip, submission_members


COMPLETE_REPORT = """# Final full-dataset model usage report
Provider: Google Gemini Developer API.
Total API calls: 3
Total tokens: 100
Estimated Standard paid-list cost: $0.001000 total
"""


def make_code_tree(root: Path) -> Path:
    code = root / "code"
    files = {
        "README.md": "run instructions\n",
        "evidence_manifest.json": json.dumps({
            "sample_only": False, "status": "candidate_facts_ready",
            "input_sha256": {"dataset": "hash"}, "source_results": {"message_1": []},
            "blocked_sources": {},
        }),
        "main.py": "print('ok')\n",
        "package_submission.py": "# packaging entry point\n",
        "buy_or_wait/__init__.py": "",
        "buy_or_wait/core.py": "VALUE = 1\n",
        "evaluation/main.py": "print('evaluate')\n",
        "evaluation/usage_report.md": COMPLETE_REPORT,
        ".env": "API_KEY=secret\n",
        "log.txt": "private transcript\n",
        "runs/result.py": "do_not_include = True\n",
        "buy_or_wait/RUNS/upper.py": "do_not_include = True\n",
        ".cache/response.py": "do_not_include = True\n",
        "buy_or_wait/__pycache__/core.py": "do_not_include = True\n",
        "tests/test_core.py": "do_not_include = True\n",
        "diagnostic.py": "do_not_include = True\n",
    }
    for name, content in files.items():
        path = code / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return code


class PackagingTests(unittest.TestCase):
    def test_member_allowlist_excludes_secrets_caches_runs_tests_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as folder:
            code = make_code_tree(Path(folder))
            names = [path.as_posix() for path in submission_members(code)]
            self.assertEqual([
                "README.md", "buy_or_wait/__init__.py", "buy_or_wait/core.py",
                "evaluation/main.py", "evaluation/usage_report.md",
                "evidence_manifest.json", "main.py", "package_submission.py",
            ], names)
            self.assertFalse(any("secret" in (code / name).read_text(encoding="utf-8") for name in names))

    def test_archives_are_byte_for_byte_reproducible_with_fixed_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = make_code_tree(root)
            first, second = root / "first.zip", root / "second.zip"
            build_code_zip(code, first)
            build_code_zip(code, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(sorted(archive.namelist()), archive.namelist())
                self.assertTrue(all(item.date_time == FIXED_TIMESTAMP for item in archive.infolist()))

    def test_incomplete_usage_report_blocks_packaging(self):
        with tempfile.TemporaryDirectory() as folder:
            code = make_code_tree(Path(folder))
            (code / "evaluation" / "usage_report.md").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(PackagingError, "not a completed"):
                submission_members(code)

    def test_incomplete_evidence_manifest_blocks_packaging(self):
        with tempfile.TemporaryDirectory() as folder:
            code = make_code_tree(Path(folder))
            (code / "evidence_manifest.json").write_text(
                json.dumps({"status": "quota_blocked"}), encoding="utf-8"
            )
            with self.assertRaisesRegex(PackagingError, "not a complete"):
                submission_members(code)

    def test_existing_destination_is_preserved_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = make_code_tree(root)
            destination = root / "code.zip"
            destination.write_bytes(b"existing")
            with self.assertRaisesRegex(PackagingError, "already exists"):
                build_code_zip(code, destination)
            self.assertEqual(b"existing", destination.read_bytes())

    def test_requires_zip_suffix(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(PackagingError, "zip suffix"):
                build_code_zip(make_code_tree(root), root / "archive.bin")


if __name__ == "__main__":
    unittest.main()
