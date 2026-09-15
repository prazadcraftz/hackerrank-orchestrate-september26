"""Terminal entry point for auditing, extracting evidence, and making decisions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from buy_or_wait.audit import audit
from buy_or_wait.contracts import ContractError, OUTPUT_COLUMNS
from buy_or_wait.data import Dataset, read_csv
from buy_or_wait.evaluator import evaluate
from buy_or_wait.extract import extract_all
from buy_or_wait.cache_audit import audit_cache, consolidate_cache
from buy_or_wait.gemini import EvidenceBlocked
from buy_or_wait.environment import load_credentials
from buy_or_wait.evidence_resolution import load_report, resolve_candidates
from buy_or_wait.manifest import bundle_evidence_manifest
from buy_or_wait.reviewed_images import load_reviewed_images, merge_reviewed_images
from buy_or_wait.runner import run_predictions


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Buy or Wait? financial decision agent')
    parser.add_argument('--dataset', type=Path, default=Path(__file__).resolve().parent.parent / 'dataset')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('audit')
    cache_audit = sub.add_parser('cache-audit')
    cache_audit.add_argument('--samples', action='store_true')
    cache_audit.add_argument('--cache', type=Path, default=Path(__file__).resolve().parent / '.cache' / 'gemini')
    consolidation = sub.add_parser('consolidate-cache')
    consolidation.add_argument('--samples', action='store_true')
    consolidation.add_argument('--cache', type=Path, default=Path(__file__).resolve().parent / '.cache' / 'gemini')
    consolidation.add_argument('--report', type=Path, required=True)
    bundling = sub.add_parser('bundle-evidence')
    bundling.add_argument('--evidence', type=Path, required=True)
    bundling.add_argument('--output', type=Path,
                          default=Path(__file__).resolve().parent / 'evidence_manifest.json')
    score = sub.add_parser('evaluate')
    score.add_argument('predictions', type=Path)
    extraction = sub.add_parser('extract')
    extraction.add_argument('--samples', action='store_true')
    extraction.add_argument('--max-calls', type=int, default=600)
    extraction.add_argument('--cache', type=Path, default=Path(__file__).resolve().parent / '.cache' / 'gemini')
    extraction.add_argument('--report', type=Path, default=Path(__file__).resolve().parent / 'runs' / 'evidence.json')
    prediction = sub.add_parser('predict')
    prediction.add_argument('--evidence',type=Path,required=True)
    prediction.add_argument('--output',type=Path,required=True)
    prediction.add_argument('--trace',type=Path,required=True)
    prediction.add_argument('--expense-policy',choices=('latest','mean','p75','maximum'),required=True)
    prediction.add_argument('--reviewed-images',type=Path,
                            help='Explicit SHA-256-bound local image-review manifest')
    args = parser.parse_args(argv)
    if args.command is None:
        code_dir = Path(__file__).resolve().parent
        args.command = 'predict'
        args.evidence = code_dir / 'evidence_manifest.json'
        args.output = code_dir.parent / 'output.csv'
        args.trace = code_dir / 'runs' / 'final-trace.json'
        args.expense_policy = 'latest'
        args.reviewed_images = None
    data = Dataset(args.dataset)
    if args.command == 'audit':
        report = audit(data)
        failed = bool(report['errors'])
    elif args.command == 'cache-audit':
        report = audit_cache(data,args.cache,sample_only=args.samples)
        failed = False
    elif args.command == 'consolidate-cache':
        result=consolidate_cache(data,args.cache,args.report,sample_only=args.samples)
        report={'status':result['status'],'report':str(args.report),
                'sources_processed':len(result['source_results']),
                'blocked_count':len(result['blocked_sources'])}
        failed=False
    elif args.command == 'bundle-evidence':
        try:
            result = bundle_evidence_manifest(data, args.evidence, args.output)
            report = {'status': 'bundled', 'output': str(args.output),
                      'sources': len(result['source_results'])}
            failed = False
        except (OSError, UnicodeError, json.JSONDecodeError, ContractError) as exc:
            report = {'status': 'blocked', 'reason': str(exc), 'output': ''}
            failed = True
    elif args.command == 'evaluate':
        report = evaluate(read_csv(args.predictions, OUTPUT_COLUMNS), data)
        failed = bool(report['missing_ids'] or report['extra_ids'] or report['static_contract_errors'])
    elif args.command == 'extract':
        load_credentials(Path(__file__).resolve().parent.parent / '.env')
        try:
            result = extract_all(data, args.cache, args.report, sample_only=args.samples, max_calls=args.max_calls)
            report = {'status': result['status'], 'report': str(args.report),
                      'sources_processed': len(result['source_results']), 'blocked': result['blocked_sources']}
            failed = result['status'] != 'candidate_facts_ready'
        except EvidenceBlocked as exc:
            report = {'status': 'blocked', 'reason': str(exc)}
            failed = True
    else:
        try:
            evidence_report=load_report(args.evidence,data)
            if args.reviewed_images:
                reviewed=load_reviewed_images(args.reviewed_images,data)
                evidence_report=merge_reviewed_images(evidence_report,reviewed)
            evidence=resolve_candidates(evidence_report,data)
            result=run_predictions(data,evidence,args.output,args.trace,expense_policy=args.expense_policy)
            report={'status':result['status'],'rows_completed':result['rows_completed'],
                    'blocked':result['blocked'],'output':str(args.output) if not result['blocked'] else ''}
            failed=bool(result['blocked'])
        except (OSError, UnicodeError, json.JSONDecodeError, ContractError, ValueError) as exc:
            report={'status':'blocked','reason':str(exc),'output':''}
            failed=True
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
