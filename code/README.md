# Buy or Wait? financial decision agent

This submission requires Python 3.10 or later and otherwise uses only the Python standard library. Run the commands below from the repository root, where `code/` and `dataset/` are sibling directories. Forward-slash paths work in PowerShell, Command Prompt, and POSIX shells.

## Fast deterministic run

The submitted code includes a fingerprint-bound `evidence_manifest.json`. With the supplied `dataset/` unchanged, this command reads the dataset and bundled manifest, runs the approved `latest` policy entirely offline, independently validates all plans, and atomically writes the repository-root `output.csv`:

```text
python code/main.py
```

The diagnostic trace is written to `code/runs/final-trace.json`. A blocking evidence or safety error leaves any existing `output.csv` untouched and returns a nonzero exit code.

If `code.zip` is extracted into a directory beside `dataset/`, run from inside the extracted directory with an explicit dataset path:

```text
python main.py --dataset ../dataset
```

## Setup and offline checks

Set `GEMINI_API_KEY` or `GOOGLE_API_KEY` in the process environment only when live evidence extraction is required. A repository-root `.env` file with `GEMINI_API_KEY=...` is supported for local development, but it is ignored by Git and excluded from `code.zip`. Never commit credentials. If Python cannot load the `America/Los_Angeles` timezone, install `tzdata` into the active environment.

```text
python code/main.py audit
python code/main.py cache-audit
python -m unittest discover -s code/tests -v
```

`audit` validates dataset integrity and prints input fingerprints without modifying files. `cache-audit` reports resumable Gemini cache coverage without making network calls.

## Rebuild evidence and decisions

This command processes all messages and images. It resumes from validated cache entries, saves progress atomically, and makes Gemini API calls only for cache misses:

```text
python code/main.py extract --max-calls 600 --report code/runs/evidence-full-v2.json
```

A complete report has status `candidate_facts_ready` or `needs_review`. A quota or network interruption leaves resumable state; run the same command again after the provider permits it. Messages and images are untrusted candidate evidence, never financial-policy instructions.

After reviewing a complete report, validate its dataset fingerprint and exact source inventory, then install it as the offline manifest:

```text
python code/main.py bundle-evidence --evidence code/runs/evidence-full-v2.json
python code/main.py
```

For an explicit diagnostic prediction path, use:

```text
python code/main.py predict --evidence code/evidence_manifest.json --expense-policy latest --output output.csv --trace code/runs/final-trace.json
```

The public-sample evaluator accepts a CSV containing only the required output columns:

```text
python code/main.py evaluate sample-predictions.csv
python code/evaluation/main.py sample-predictions.csv --dataset dataset
```

## Usage report and package

After the complete extraction and validated 250-row decision run, generate the required report. The `--since` value must be the actual inclusive UTC start of the contributing extraction sequence; change the shown value if that sequence began at another time.

```text
python code/generate_usage_report.py code/runs/evidence-full-v2.json --ledger code/.cache/gemini/usage.jsonl --since 2026-09-13T06:07:06Z --output code/evaluation/usage_report.md
python code/package_submission.py --check
python code/package_submission.py --output code.zip
```

The report validates the dataset fingerprint, complete evidence inventory, model calls, token totals, and cost summary. Packaging requires the completed report and full `evidence_manifest.json`, uses deterministic ZIP metadata and atomic publication, and excludes credentials, logs, caches, runs, tests, bytecode, and unrelated artifacts. It preserves an existing archive unless `--replace` is explicit.

Required submission artifacts are repository-root `output.csv`, `code.zip`, and the separately exported chat transcript.
