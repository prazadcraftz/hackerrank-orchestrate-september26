"""Candidate generation on a resolved forecast; no evidence or recurrence guessing."""
from dataclasses import dataclass
from decimal import Decimal

from .cashflow import CashState, capacity, replay
from .contracts import ContractError, iso_date, money, numeric_id, option_schedule


@dataclass(frozen=True)
class Candidate:
    method: str
    payments: tuple
    option_id: str = ''
    changes: tuple[str, ...] = ()
    reduction: Decimal = Decimal('0')


def rank(candidate: Candidate, deadline):
    """Official priorities first; secondary change ties never outrank them.

    Non-offer methods have no supplied option ID and sort after real option IDs
    when all preceding criteria tie. Not an invented seller payment option.
    """
    if not candidate.payments:
        raise ContractError('Cannot rank an empty candidate')
    return (candidate.payments[-1][0] > deadline, bool(candidate.changes),
            sum((p[1] for p in candidate.payments), Decimal('0')),
            candidate.payments[0][0], len(candidate.payments),
            numeric_id(candidate.option_id) if candidate.option_id else float('inf'),
            len(candidate.changes), candidate.reduction, candidate.changes, candidate.method)


def no_change_candidates(state: CashState, request, profile, options, *, installment_eligible):
    """Return replay-verified candidates plus rejected reasons and baseline capacity.

    The caller must supply the explicit installment-duration policy. Unknown policy
    is not silently replaced by payment count, elapsed days, or calendar months.
    This function only generates no-change plans; it cannot conclude unaffordability
    until the separate legal spending-change search is also exhausted.
    """
    if state.start != iso_date(request['request_date']):
        raise ContractError('Forecast start differs from request')
    requested = money(request['requested_amount'], allow_zero=False)
    deadline = iso_date(request['desired_completion_date'])
    accepted = set(profile['payment_methods_user_will_consider'].split('|'))
    baseline = capacity(state, requested)
    raw, rejected, valid = [], [], []
    earliest, safe = baseline['earliest_full'], baseline['safe_today']
    if 'full_payment' in accepted:
        raw.append(Candidate('full_payment', ((state.start, requested),)))
        if earliest is not None and earliest > state.start:
            raw.append(Candidate('wait', ((earliest, requested),)))
    if ('partial_payment' in accepted and request['allows_partial_payment'] == 'true'
            and Decimal('0') < safe < requested and earliest is not None and earliest > state.start):
        raw.append(Candidate('partial_payment', ((state.start, safe), (earliest, requested-safe))))
    for option in options:
        if option['request_id'] != request['request_id']:
            raise ContractError('Cross-request payment option')
        if option['payment_method'] != 'installments':
            continue
        schedule = tuple(option_schedule(option))
        if (sum((amount for _, amount in schedule), Decimal('0')) != money(option['total_payable_amount'])
                or money(option['total_payable_amount']) != requested + money(option['financing_fee'])):
            raise ContractError('Inconsistent installment amount/fee total')
        if ('installments' not in accepted or not profile['max_installment_months']
                or not installment_eligible(option, profile)):
            rejected.append({'option_id': option['payment_option_id'], 'reason': 'installment_ineligible'})
        else:
            raw.append(Candidate('installments', schedule, option['payment_option_id']))
    for candidate in raw:
        if any(not state.start <= d <= min(deadline, state.end) for d, _ in candidate.payments):
            rejected.append({'method': candidate.method, 'option_id': candidate.option_id, 'reason': 'outside_window'})
            continue
        if not replay(state, list(candidate.payments))['safe']:
            rejected.append({'method': candidate.method, 'option_id': candidate.option_id, 'reason': 'minimum_balance_breach'})
            continue
        valid.append(candidate)
    return {'candidates': sorted(valid, key=lambda c: rank(c, deadline)),
            'rejected': rejected, 'capacity': baseline}
