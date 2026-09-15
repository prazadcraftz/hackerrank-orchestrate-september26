"""Field-level local diagnostics, not an estimate of the hidden scoring formula."""
from __future__ import annotations

from collections import Counter
from decimal import Decimal

from .contracts import OUTPUT_COLUMNS, ContractError, iso_date, money, parse_plan, static_errors
from .data import Dataset, unique


def evaluate(predictions: list[dict], data: Dataset) -> dict:
    truth = unique(data.tables['sample_requests'], 'request_id')
    predicted = unique(predictions, 'request_id')
    metrics = {field: Counter() for field in OUTPUT_COLUMNS[1:-1]}
    diffs, invalid, abs_amount_errors, date_errors = {}, {}, [], []
    status_confusion, method_confusion = Counter(), Counter()
    for rid, gold in truth.items():
        if rid not in predicted:
            continue
        row, req = predicted[rid], data.requests[rid]
        errors = static_errors(row, req, data.profiles[req['user_id']], data.options_by_request[rid], data.events)
        if errors:
            invalid[rid] = errors
        mismatches = {}
        for field in metrics:
            actual, expected = row.get(field, ''), gold[field]
            equal = actual == expected
            try:
                if field == 'amount_safe_to_pay':
                    difference = abs(money(actual) - money(expected))
                    abs_amount_errors.append(difference)
                    equal = difference == 0
                    metrics[field]['within_1_percent'] += int(difference <= money(expected) * Decimal('.01'))
                elif field == 'payment_plan':
                    equal = parse_plan(actual) == parse_plan(expected)
                elif field == 'earliest_date_for_full_payment' and actual and expected:
                    date_errors.append(abs((iso_date(actual) - iso_date(expected)).days))
                elif field == 'spending_changes_needed':
                    def normalize(value):
                        if value == 'none':
                            return ()
                        items = []
                        for change in value.split('|'):
                            p = change.split(':')
                            if len(p) == 3 and p[0] == 'reduce_to':
                                items.append((p[0], p[1], money(p[2])))
                            elif len(p) == 2 and p[0] == 'stop':
                                items.append((p[0], p[1]))
                            else:
                                raise ContractError('Invalid change')
                        return tuple(sorted(items))
                    equal = normalize(actual) == normalize(expected)
            except (ContractError, ValueError):
                equal = False
            metrics[field]['compared'] += 1
            metrics[field]['matches'] += int(equal)
            if not equal:
                mismatches[field] = {'expected': expected, 'actual': actual}
        if mismatches:
            diffs[rid] = mismatches
        status_confusion[f'{gold["affordability_status"]} -> {row.get("affordability_status")}'] += 1
        method_confusion[f'{gold["recommended_payment_method"]} -> {row.get("recommended_payment_method")}'] += 1
    return {
        'scope': 'Solved samples only. No hidden-score estimate. No independent financial replay yet.',
        'expected_rows': len(truth), 'provided_rows': len(predicted),
        'missing_ids': sorted(truth.keys() - predicted.keys()),
        'extra_ids': sorted(predicted.keys() - truth.keys()),
        'metrics': {field: dict(count) for field, count in metrics.items()},
        'amount_mean_absolute_error': str(sum(abs_amount_errors) / len(abs_amount_errors)) if abs_amount_errors else None,
        'amount_max_absolute_error': str(max(abs_amount_errors)) if abs_amount_errors else None,
        'date_mean_absolute_error_days': sum(date_errors) / len(date_errors) if date_errors else None,
        'date_error_comparable_rows': len(date_errors),
        'status_confusion': dict(status_confusion), 'method_confusion': dict(method_confusion),
        'static_contract_errors': invalid, 'field_mismatches': diffs,
        'explanation_checks': 'Only nonempty text checked here; factual consistency requires the frozen decision trace.',
    }
