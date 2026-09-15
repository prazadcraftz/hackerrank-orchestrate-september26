"""Auditable recurrence proposals; callers must resolve amendments before use.

Neither a detected cadence nor a repeated credit proves future income. This module
only describes observed patterns and generates dates under an explicit convention.
"""
from calendar import monthrange
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from .contracts import ContractError


@dataclass(frozen=True)
class Cadence:
    kind: str
    interval: int
    anchor: date
    support: int
    observations: int


def infer_cadence(dates: list[date]) -> Cadence | None:
    """Require >=3 distinct occurrences and >=80% gap support.

    Monthly dates can clamp at month-end. Fixed-day patterns tolerate at most one
    day's jitter. Duplicate dates are ambiguity, not recurrence evidence.
    """
    if len(dates) < 3 or len(set(dates)) != len(dates):
        return None
    dates = sorted(dates)
    months = [d.year*12+d.month for d in dates]
    gaps = [(b-a).days for a,b in zip(dates, dates[1:])]
    threshold = (4*len(gaps)+4)//5
    month_support = sum(b-a == 1 for a,b in zip(months, months[1:]))
    anchor_day = max(d.day for d in dates)
    clamped_support = sum(d.day == min(anchor_day, monthrange(d.year,d.month)[1]) for d in dates)
    if month_support >= threshold and clamped_support >= (4*len(dates)+4)//5:
        # Preserve nominal anchor day even when latest date is February 28.
        anchor = next(d for d in reversed(dates) if d.day == anchor_day)
        return Cadence('monthly', 1, anchor, month_support, len(dates))
    step = int(median(gaps))
    support = sum(abs(g-step) <= 1 for g in gaps)
    if 2 <= step <= 35 and support >= threshold:
        return Cadence('days', step, dates[-1], support, len(dates))
    return None


def occurrence_dates(cadence: Cadence, *, after: date, through: date):
    """Generate strictly after the last known occurrence through inclusive end."""
    if cadence.kind == 'monthly':
        month = after.year*12+after.month-1
        while True:
            year, index = divmod(month,12)
            day = date(year,index+1,min(cadence.anchor.day,monthrange(year,index+1)[1]))
            if day > through:
                return
            if day > after:
                yield day
            month += 1
    elif cadence.kind == 'days' and cadence.interval > 0:
        day = cadence.anchor
        if day <= after:
            day += timedelta(days=((after-day).days//cadence.interval+1)*cadence.interval)
        while day <= through:
            yield day
            day += timedelta(days=cadence.interval)
    else:
        raise ContractError('Unknown cadence')


def expense_estimate(amounts: list[Decimal], *, policy: str) -> Decimal:
    """Explicit experimental estimators; no silently selected financial policy."""
    if not amounts or any(not isinstance(a,Decimal) or not a.is_finite() or a < 0 for a in amounts):
        raise ContractError('Resolved finite nonnegative expense observations required')
    if policy == 'latest':
        return amounts[-1]
    if policy == 'mean':
        return sum(amounts)/len(amounts)
    if policy == 'maximum':
        return max(amounts)
    if policy == 'p75':
        return sorted(amounts)[(3*len(amounts)+3)//4-1]
    raise ContractError('Explicit supported expense policy required')
