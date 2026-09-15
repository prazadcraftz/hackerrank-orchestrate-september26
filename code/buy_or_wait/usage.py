"""Create the required final-run token and list-price report."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

PRICES = {
    'gemini-3.5-flash-lite': (0.30, 2.50),
    'gemini-3.6-flash': (0.75, 3.75),
    'gemini-3.1-pro-preview': (2.00, 12.00),
}
PRICING_URL = 'https://ai.google.dev/gemini-api/docs/pricing'
OPERATIONS = frozenset({'countTokens', 'generateContent'})
STATUSES = frozenset({'ok', 'failed'})


def _timestamp(value, field='time'):
    if not isinstance(value, str) or not value:
        raise ValueError(f'Usage {field} must be a non-empty ISO timestamp')
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'Usage {field} is not a valid ISO timestamp') from exc
    if stamp.tzinfo is None:
        raise ValueError(f'Usage {field} must include timezone')
    return stamp


def _token(value, field, *, required=True):
    if value is None and not required:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f'Usage {field} must be a non-negative integer')
    return value


def _validate_record(record):
    if not isinstance(record, dict):
        raise ValueError('Each usage record must be an object')
    model = record.get('model')
    if model not in PRICES:
        raise ValueError(f'Usage contains an unpriced or unknown model: {model!r}')
    operation = record.get('operation')
    if operation not in OPERATIONS:
        raise ValueError(f'Usage contains an unknown operation: {operation!r}')
    status = record.get('status')
    if status not in STATUSES:
        raise ValueError(f'Usage contains an unfinished or unknown status: {status!r}')
    stamp = _timestamp(record.get('time'))

    # A failed request has no provider-confirmed generation usage. In particular,
    # the local preflight token reservation is not evidence that Google billed it.
    if operation != 'generateContent' or status != 'ok':
        return model, operation, status, stamp, 0, 0, 0

    usage = record.get('usage')
    if not isinstance(usage, dict):
        raise ValueError('Successful generation is missing usage metadata')
    input_tokens = _token(usage.get('promptTokenCount'), 'promptTokenCount')
    candidate_tokens = _token(usage.get('candidatesTokenCount'), 'candidatesTokenCount')
    thinking_tokens = _token(usage.get('thoughtsTokenCount'), 'thoughtsTokenCount', required=False)
    output_tokens = candidate_tokens + thinking_tokens
    if 'totalTokenCount' in usage:
        total_tokens = _token(usage['totalTokenCount'], 'totalTokenCount')
        if total_tokens != input_tokens + output_tokens:
            raise ValueError('Usage totalTokenCount disagrees with prompt, candidate, and thinking tokens')
    return model, operation, status, stamp, input_tokens, output_tokens, thinking_tokens


def summarize_usage(paths, *, evaluation_requests=250):
    records = []
    cache_hits = 0
    seen = set()
    for path in paths:
        report = json.loads(path.read_text(encoding='utf-8'))
        cache_hits += (int(report.get('cache_hits_previous_runs', 0)) +
                       int(report.get('cache_hits_this_run', 0)))
        for record in report.get('usage_previous_runs', []) + report.get('usage_this_run', []):
            identity = json.dumps(record, sort_keys=True, separators=(',', ':'))
            if identity not in seen:
                seen.add(identity)
                records.append(record)
    return summarize_records(records, cache_hits=cache_hits,
                             evaluation_requests=evaluation_requests)


def summarize_ledger(path, *, since, cache_hits=0, evaluation_requests=250):
    cutoff = _timestamp(since, 'cutoff')
    records = []
    with path.open(encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'Invalid usage ledger JSON on line {line_number}') from exc
            if not isinstance(record, dict):
                raise ValueError(f'Usage ledger line {line_number} must be an object')
            stamp = _timestamp(record.get('time'))
            if stamp >= cutoff:
                records.append(record)
    return summarize_records(records, cache_hits=cache_hits,
                             evaluation_requests=evaluation_requests)


def summarize_records(records, *, cache_hits, evaluation_requests):
    if not isinstance(evaluation_requests, int) or isinstance(evaluation_requests, bool) or evaluation_requests <= 0:
        raise ValueError('Evaluation request count must be a positive integer')
    if not isinstance(cache_hits, int) or isinstance(cache_hits, bool) or cache_hits < 0:
        raise ValueError('Cache-hit count must be a non-negative integer')
    per_model = defaultdict(lambda: {'api_calls': 0, 'generation_calls': 0, 'failed_calls': 0,
                                     'input_tokens': 0, 'output_tokens': 0, 'thinking_tokens': 0})
    timestamps = []
    for record in records:
        model, operation, status, stamp, input_tokens, output_tokens, thinking_tokens = _validate_record(record)
        timestamps.append(stamp)
        item = per_model[model]
        item['api_calls'] += 1
        item['failed_calls'] += status != 'ok'
        if operation == 'generateContent':
            item['generation_calls'] += 1
            item['input_tokens'] += input_tokens
            item['output_tokens'] += output_tokens
            item['thinking_tokens'] += thinking_tokens
    if not timestamps or not any(item['generation_calls'] for item in per_model.values()):
        raise ValueError('No generation calls were found for the final contributing run')
    for model, item in per_model.items():
        input_price, output_price = PRICES[model]
        item['total_tokens'] = item['input_tokens'] + item['output_tokens']
        item['list_price_usd'] = (item['input_tokens'] / 1_000_000 * input_price +
                                  item['output_tokens'] / 1_000_000 * output_price)
    total = {key: sum(item[key] for item in per_model.values()) for key in
             ('api_calls', 'generation_calls', 'failed_calls', 'input_tokens', 'output_tokens',
              'thinking_tokens', 'total_tokens', 'list_price_usd')}
    total['average_tokens_per_request'] = total['total_tokens'] / evaluation_requests
    total['list_price_per_request_usd'] = total['list_price_usd'] / evaluation_requests
    return {'per_model': dict(per_model), 'total': total, 'cache_hits': cache_hits,
            'evaluation_requests': evaluation_requests,
            'run_started_at': min(timestamps).isoformat(),
            'run_ended_at': max(timestamps).isoformat()}


def render_usage(summary):
    lines = ['# Final full-dataset model usage report', '',
        f"Contributing API-call window: {summary['run_started_at']} through {summary['run_ended_at']}", '',
        'Provider: Google Gemini Developer API. Models extract candidate evidence only; deterministic code makes and validates decisions.', '',
        '| Model | API calls | Generations | Failed | Input tokens | Output incl. thinking | Thinking | Total tokens | Standard paid-list estimate (USD) |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for model, item in sorted(summary['per_model'].items()):
        lines.append(f"| {model} | {item['api_calls']} | {item['generation_calls']} | {item['failed_calls']} | {item['input_tokens']} | {item['output_tokens']} | {item['thinking_tokens']} | {item['total_tokens']} | ${item['list_price_usd']:.6f} |")
    total = summary['total']
    lines += ['', f"Evaluation requests: {summary['evaluation_requests']}",
        f"Total API calls: {total['api_calls']} ({total['generation_calls']} generation calls; {total['failed_calls']} failed)",
        f"Total tokens: {total['total_tokens']} ({total['input_tokens']} input; {total['output_tokens']} output including thinking)",
        f"Average tokens per evaluation request: {total['average_tokens_per_request']:.2f}",
        f"Estimated Standard paid-list cost: ${total['list_price_usd']:.6f} total; ${total['list_price_per_request_usd']:.8f} per evaluation request",
        f"Cache hits during the contributing runs: {summary['cache_hits']}", '',
        f'Pricing source checked 2026-09-13: {PRICING_URL}', '',
        'Cost note: Google lists free input/output for these models on eligible free-tier usage. The estimate above applies the published Standard paid-list rates to measured tokens so it remains conservative; actual billing tier is not exposed by the response metadata and may be zero. Gemini 3.6 Flash prices shown are the rates published through December 31, 2026. Failed calls and countTokens calls have no provider-confirmed generation usage and add no token cost here.', '',
        'Cache note: the full run reused validated sample-source caches. This report combines the original cache-producing sample run with the remaining full extraction and deduplicates call records. Cache hits did not trigger new provider calls.']
    return '\n'.join(lines) + '\n'
