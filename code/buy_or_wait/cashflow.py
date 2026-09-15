"""Exact, policy-explicit cash-flow arithmetic, independent of evidence inference.

Callers supply resolved home-currency flows and an inclusive horizon. This module
does not guess recurrence, settle pending credits, or resolve financial evidence.
Payments occur after the day's ordinary flows. Intraday ordering is mandatory.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR

from .contracts import ContractError

ZERO = Decimal('0')
CENT = Decimal('0.01')


@dataclass(frozen=True)
class Flow:
    identity: str
    day: date
    amount: Decimal  # signed home-currency cash movement
    reason: str

    def __post_init__(self):
        if not self.identity or not self.reason or not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise ContractError('Flows require identity, reason and finite Decimal amount')


@dataclass(frozen=True)
class CashState:
    start: date
    end: date
    opening: Decimal
    minimum: Decimal
    flows: tuple[Flow, ...]
    intraday: str

    def __post_init__(self):
        if self.end < self.start or self.intraday not in {'debits_first', 'credits_first'}:
            raise ContractError('Explicit valid horizon and intraday policy required')
        if any(not isinstance(x, Decimal) or not x.is_finite() or x < 0 for x in (self.opening, self.minimum)):
            raise ContractError('Opening and minimum must be nonnegative finite Decimal')
        if len({f.identity for f in self.flows}) != len(self.flows):
            raise ContractError('Duplicate cash-flow identity')
        if any(not self.start <= f.day <= self.end for f in self.flows):
            raise ContractError('Flow outside validated horizon')


def ordered_flows(state):
    def key(f):
        credit = f.amount >= 0
        phase = int(credit) if state.intraday == 'debits_first' else int(not credit)
        return f.day, phase, f.identity
    return sorted(state.flows, key=key)


def capacity(state: CashState, requested: Decimal) -> dict:
    """Capacity for one end-of-day payment; earlier breaches cannot be cured by waiting.

    Suffix minima include each later intermediate movement, not just day-end net
    balances. The minimum at a payment point excludes earlier movements that day.
    """
    if not isinstance(requested, Decimal) or not requested.is_finite() or requested <= 0:
        raise ContractError('Requested amount must be positive finite Decimal')
    grouped = {}
    for f in ordered_flows(state):
        grouped.setdefault(f.day, []).append(f)
    points = [state.opening]
    payment_points = {}
    balance = state.opening
    day = state.start
    while day <= state.end:
        for flow in grouped.get(day, []):
            balance += flow.amount
            points.append(balance)
        points.append(balance)
        payment_points[day] = len(points) - 1
        day += timedelta(days=1)
    suffix = [ZERO] * len(points)
    low = points[-1]
    for i in range(len(points) - 1, -1, -1):
        low = min(low, points[i])
        suffix[i] = low
    baseline_safe = min(points) >= state.minimum
    available = {}
    for day, i in payment_points.items():
        raw = max(ZERO, suffix[i] - state.minimum) if baseline_safe else ZERO
        available[day] = min(requested, raw).quantize(CENT, rounding=ROUND_FLOOR)
    earliest = next((d for d, amount in available.items() if amount >= requested), None)
    return {'baseline_safe': baseline_safe, 'minimum_balance': min(points),
            'safe_today': available[state.start], 'earliest_full': earliest,
            'capacity_by_date': available}


def replay(state: CashState, payments: list[tuple[date, Decimal]]) -> dict:
    """Independent forward replay. Reject malformed/out-of-coverage schedules.

    Does not call capacity or ordered_flows, so arithmetic/ordering regressions in
    the capacity implementation can be detected by comparisons in tests.
    """
    if payments != sorted(payments, key=lambda p: p[0]):
        raise ContractError('Payments must be chronological')
    for day, amount in payments:
        if not state.start <= day <= state.end:
            raise ContractError('Payment outside validated horizon')
        if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
            raise ContractError('Payment must be positive finite Decimal')
    balance = state.opening
    low = balance
    trace = [{'date': state.start.isoformat(), 'kind': 'opening', 'balance': str(balance)}]
    day = state.start
    while day <= state.end:
        ordinary = [f for f in state.flows if f.day == day]
        debits = sorted((f for f in ordinary if f.amount < 0), key=lambda f: f.identity)
        credits = sorted((f for f in ordinary if f.amount >= 0), key=lambda f: f.identity)
        batches = (debits, credits) if state.intraday == 'debits_first' else (credits, debits)
        for batch in batches:
            for f in batch:
                balance += f.amount
                low = min(low, balance)
                trace.append({'date': day.isoformat(), 'kind': 'flow', 'id': f.identity,
                              'reason': f.reason, 'amount': str(f.amount), 'balance': str(balance)})
        for paid_day, amount in payments:
            if paid_day == day:
                balance -= amount
                low = min(low, balance)
                trace.append({'date': day.isoformat(), 'kind': 'payment',
                              'amount': str(amount), 'balance': str(balance)})
        day += timedelta(days=1)
    return {'safe': low >= state.minimum, 'minimum_balance': low,
            'closing_balance': balance, 'trace': trace}
