"""Generate usage_report.md only from complete contributing extraction runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from buy_or_wait.data import Dataset
from buy_or_wait.usage import render_usage, summarize_ledger, summarize_usage

REPO_ROOT = Path(__file__).resolve().parent.parent


def _expected_sources(data, *, sample_only):
    if not sample_only:
        return set(data.messages) | set(data.images)
    sample_users = {row['user_id'] for row in data.tables['sample_requests']}
    return ({key for key, row in data.messages.items() if row['user_id'] in sample_users} |
            {key for key, row in data.images.items() if row['user_id'] in sample_users})


def validate_reports(reports, data, *, expected_full_sources=None):
    full = [report for report in reports if report.get('sample_only') is False]
    if len(full) != 1:
        raise ValueError('Exactly one completed full extraction report is required')
    fingerprint = data.fingerprint()
    all_sources = set(data.messages) | set(data.images)
    if expected_full_sources is not None and expected_full_sources != len(all_sources):
        raise ValueError('Configured full-source count differs from the dataset evidence inventory')
    for report in reports:
        sample_only = report.get('sample_only')
        if not isinstance(sample_only, bool):
            raise ValueError('Every extraction report must declare sample_only as a boolean')
        if report.get('input_sha256') != fingerprint:
            raise ValueError('Extraction report fingerprint differs from the current dataset')
        status = report.get('status')
        if status not in {'candidate_facts_ready', 'needs_review'}:
            raise ValueError('Extraction report is not complete')
        source_results = report.get('source_results')
        blocked_sources = report.get('blocked_sources')
        if not isinstance(source_results, dict) or not isinstance(blocked_sources, dict):
            raise ValueError('Extraction report source results and blocked sources must be objects')
        expected = _expected_sources(data, sample_only=sample_only)
        if set(source_results) != expected:
            raise ValueError('Extraction report source identities differ from the expected evidence inventory')
        if not set(blocked_sources) <= expected:
            raise ValueError('Extraction report has blocked identities outside its evidence inventory')
        if (status == 'candidate_facts_ready') != (not blocked_sources):
            raise ValueError('Extraction report status disagrees with its blocked-source inventory')
    return full[0]


def generate_report(report_paths, *, data, output, ledger=None, since=None,
                    expected_full_sources=None):
    reports = [json.loads(path.read_text(encoding='utf-8')) for path in report_paths]
    validate_reports(reports, data, expected_full_sources=expected_full_sources)
    if bool(ledger) != bool(since):
        raise ValueError('--ledger and --since must be supplied together')
    evaluation_requests = len(data.tables['requests'])
    cache_hits = sum(int(report.get('cache_hits_previous_runs', 0)) +
                     int(report.get('cache_hits_this_run', 0)) for report in reports)
    summary = (summarize_ledger(ledger, since=since, cache_hits=cache_hits,
                                evaluation_requests=evaluation_requests)
               if ledger else summarize_usage(report_paths,
                                               evaluation_requests=evaluation_requests))
    rendered = render_usage(summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_suffix(output.suffix + '.tmp')
    pending.write_text(rendered, encoding='utf-8', newline='\n')
    pending.replace(output)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('reports', nargs='+', type=Path)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parent / 'evaluation' / 'usage_report.md')
    parser.add_argument('--dataset', type=Path, default=REPO_ROOT / 'dataset')
    parser.add_argument('--expected-full-sources', type=int)
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--since', help='Inclusive ISO timestamp for the final extraction sequence')
    args = parser.parse_args(argv)
    try:
        summary = generate_report(args.reports, data=Dataset(args.dataset), output=args.output,
                                  ledger=args.ledger, since=args.since,
                                  expected_full_sources=args.expected_full_sources)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output': str(args.output), 'summary': summary}, indent=2))


if __name__ == '__main__':
    main()
