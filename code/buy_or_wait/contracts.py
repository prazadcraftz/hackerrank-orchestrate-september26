"""Strict parsing and static contract checks; does not claim cash-flow safety."""
from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

OUTPUT_COLUMNS = (
    'request_id', 'amount_safe_to_pay', 'affordability_status',
    'recommended_payment_method', 'payment_plan',
    'earliest_date_for_full_payment', 'spending_changes_needed',
    'decision_explanation',
)
REQUEST_COLUMNS = (
    'request_id', 'user_id', 'request_date', 'request_type', 'requested_amount',
    'desired_completion_date', 'allows_partial_payment', 'request_text',
)
STATUSES = {'affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable'}
METHODS = {'full_payment', 'partial_payment', 'installments', 'wait', 'not_recommended'}
FLEXIBILITY = {'fixed', 'stoppable', 'reducible', 'reducible_or_stoppable'}
CURRENCIES = {'INR', 'ZAR', 'IDR', 'USD', 'EUR'}


class ContractError(ValueError):
    pass


def money(value: str, *, allow_zero: bool = True) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ContractError(f'Invalid monetary value: {value!r}') from exc
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise ContractError(f'Money must be finite and nonnegative: {value!r}')
    return result


def iso_date(value: str) -> date:
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ContractError(f'Expected YYYY-MM-DD: {value!r}')
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError(f'Invalid date: {value!r}') from exc


def positive_int(value: str) -> int:
    if not re.fullmatch(r'[1-9]\d*', value):
        raise ContractError(f'Expected positive integer: {value!r}')
    return int(value)


def numeric_id(value: str) -> int:
    match = re.fullmatch(r'[a-z_]+_(\d+)', value)
    if not match:
        raise ContractError(f'Invalid identifier: {value!r}')
    return int(match.group(1))


def parse_plan(value: str) -> list[tuple[date, Decimal]]:
    if value == 'none':
        return []
    try:
        result = [(iso_date(d), money(a, allow_zero=False))
                  for d, a in (part.split(':') for part in value.split('|'))]
    except ValueError as exc:
        raise ContractError(f'Invalid payment plan: {value!r}') from exc
    if result != sorted(result, key=lambda item: item[0]):
        raise ContractError('Payment plan is not chronological')
    return result


def option_schedule(option: dict) -> list[tuple[date, Decimal]]:
    count = positive_int(option['number_of_payments'])
    first = iso_date(option['first_payment_date'])
    interval = positive_int(option['payment_frequency_days']) if count > 1 else 0
    amount = money(option['payment_amount'], allow_zero=False)
    return [(first + timedelta(days=i * interval), amount) for i in range(count)]


def static_errors(row: dict, request: dict, profile: dict,
                  options: list[dict], events: dict[str, dict], *,
                  horizon_days: int = 90) -> list[str]:
    """Checks syntax/eligibility only. Recurrence and balance require independent replay.

    Does not infer financial impossibility from an empty or invalid output.
    Duration-limit interpretation is deliberately deferred to the policy layer.
    """
    errors: list[str] = []
    if tuple(row) != OUTPUT_COLUMNS:
        errors.append('OUTPUT_COLUMNS')
    if row.get('request_id') != request['request_id']:
        errors.append('REQUEST_ID')
    try:
        safe = money(row['amount_safe_to_pay'])
        requested = money(request['requested_amount'], allow_zero=False)
        start = iso_date(request['request_date'])
        deadline = iso_date(request['desired_completion_date'])
        earliest = iso_date(row['earliest_date_for_full_payment']) if row['earliest_date_for_full_payment'] else None
        plan = parse_plan(row['payment_plan'])
    except (KeyError, ContractError) as exc:
        return errors + [f'PARSE:{exc}']
    end = start + timedelta(days=horizon_days - 1)
    status = row['affordability_status']
    method = row['recommended_payment_method']
    accepted = set(profile['payment_methods_user_will_consider'].split('|'))
    if safe > requested:
        errors.append('AMOUNT_BOUNDS')
    if status not in STATUSES:
        errors.append('STATUS')
    if method not in METHODS:
        errors.append('METHOD')
    if not row['decision_explanation'].strip():
        errors.append('EXPLANATION_EMPTY')
    if earliest and not start <= earliest <= end:
        errors.append('EARLIEST_OUTSIDE_HORIZON')
    if any(not start <= d <= min(deadline, end) for d, _ in plan):
        errors.append('PAYMENT_OUTSIDE_WINDOW')
    if method in {'full_payment', 'partial_payment', 'installments'} and method not in accepted:
        errors.append('METHOD_NOT_ACCEPTED')
    if method in {'full_payment', 'wait'}:
        expected_date = start if method == 'full_payment' else earliest
        if plan != [(expected_date, requested)]:
            errors.append('SINGLE_PAYMENT_SCHEDULE')
    if method == 'wait':
        if 'full_payment' not in accepted or earliest is None or earliest <= start:
            errors.append('WAIT_INELIGIBLE')
        if status != 'affordable_later' or row['spending_changes_needed'] != 'none':
            errors.append('WAIT_STATUS_OR_CHANGES')
    if method == 'partial_payment':
        if request['allows_partial_payment'] != 'true' or not 0 < safe < requested:
            errors.append('PARTIAL_INELIGIBLE')
        if earliest is None or earliest <= start or earliest > deadline:
            errors.append('PARTIAL_EARLIEST')
        if plan != [(start, safe), (earliest, requested - safe)]:
            errors.append('PARTIAL_SCHEDULE')
        if status != 'affordable_with_plan':
            errors.append('PARTIAL_STATUS')
    if method == 'installments':
        if not profile['max_installment_months']:
            errors.append('INSTALLMENTS_REJECTED_BY_PROFILE')
        matching = [o for o in options if o['payment_method'] == 'installments'
                    and option_schedule(o) == plan]
        if not matching:
            errors.append('INSTALLMENT_SCHEDULE')
        if status != 'affordable_with_plan':
            errors.append('INSTALLMENT_STATUS')
    if status == 'affordable_now':
        if method != 'full_payment' or safe != requested or earliest != start or row['spending_changes_needed'] != 'none':
            errors.append('AFFORDABLE_NOW_CONSISTENCY')
    if status == 'affordable_later' and method != 'wait':
        errors.append('AFFORDABLE_LATER_CONSISTENCY')
    if status == 'affordable_with_plan':
        if method not in {'full_payment', 'partial_payment', 'installments'}:
            errors.append('WITH_PLAN_METHOD')
        if method == 'full_payment' and row['spending_changes_needed'] == 'none':
            errors.append('FULL_WITH_PLAN_WITHOUT_CHANGES')
    if method == 'not_recommended' or status == 'not_affordable':
        if (method, status, row['payment_plan'], row['spending_changes_needed']) != (
                'not_recommended', 'not_affordable', 'none', 'none'):
            errors.append('NOT_AFFORDABLE_CONSISTENCY')
    if method != 'not_recommended' and not plan:
        errors.append('PLAN_MISSING')
    if row['spending_changes_needed'] != 'none':
        changes = row['spending_changes_needed'].split('|')
        if len(changes) > 3:
            errors.append('TOO_MANY_CHANGES')
        seen = set()
        for change in changes:
            parts = change.split(':')
            if len(parts) not in {2, 3} or parts[0] not in {'stop', 'reduce_to'}:
                errors.append('CHANGE_SYNTAX')
                continue
            action, event_id = parts[:2]
            if (action == 'stop' and len(parts) != 2) or (action == 'reduce_to' and len(parts) != 3):
                errors.append('CHANGE_SYNTAX')
                continue
            if event_id in seen:
                errors.append('DUPLICATE_CHANGE_TARGET')
            seen.add(event_id)
            event = events.get(event_id)
            if not event or event['user_id'] != request['user_id']:
                errors.append('CHANGE_TARGET')
                continue
            category = event['category']
            if category in profile['expense_categories_to_protect'].split('|'):
                errors.append('CHANGE_PROTECTED')
            if event['direction'] != 'debit':
                errors.append('CHANGE_NOT_EXPENSE')
            if action == 'stop':
                if (event['flexibility'] not in {'stoppable', 'reducible_or_stoppable'}
                    or category not in profile['expense_categories_user_is_willing_to_stop'].split('|')):
                    errors.append('STOP_NOT_ALLOWED')
            else:
                if (event['flexibility'] not in {'reducible', 'reducible_or_stoppable'}
                    or category not in profile['expense_categories_user_is_willing_to_reduce'].split('|')):
                    errors.append('REDUCE_NOT_ALLOWED')
                try:
                    new = money(parts[2])
                    if not event['minimum_allowed_amount']:
                        errors.append('REDUCTION_MINIMUM_UNRESOLVED')
                    elif new < money(event['minimum_allowed_amount']):
                        errors.append('REDUCTION_BELOW_MINIMUM')
                    if event['amount'] and new >= money(event['amount']):
                        errors.append('REDUCTION_NOT_LOWER')
                except ContractError:
                    errors.append('REDUCTION_AMOUNT')
    return errors
