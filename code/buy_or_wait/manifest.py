"""Validate and atomically install the evidence report bundled with code.zip."""
from __future__ import annotations

import json
from pathlib import Path

from .contracts import ContractError
from .evidence_resolution import load_report


def bundle_evidence_manifest(data, source: Path, destination: Path) -> dict:
    """Install one complete full-dataset extraction report deterministically."""
    report = load_report(source, data)
    if report.get('sample_only') is not False:
        raise ContractError('Bundled evidence must be a full-dataset extraction report')
    expected = set(data.messages) | set(data.images)
    source_results = report.get('source_results')
    blocked_sources = report.get('blocked_sources')
    if not isinstance(source_results, dict) or set(source_results) != expected:
        raise ContractError('Bundled evidence does not contain the exact source inventory')
    if not isinstance(blocked_sources, dict) or not set(blocked_sources) <= expected:
        raise ContractError('Bundled evidence has an invalid blocked-source inventory')
    if (report['status'] == 'candidate_facts_ready') != (not blocked_sources):
        raise ContractError('Bundled evidence status disagrees with blocked sources')

    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_suffix(destination.suffix + '.tmp')
    pending.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n',
                       encoding='utf-8', newline='\n')
    pending.replace(destination)
    return report
