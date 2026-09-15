"""Classify resolved explicit records without guessing recurring projections.

Snapshot includes settled history. Pending debits are reserved immediately once;
their supplied settlement date remains the FX conversion date. Only explicitly
confirmed, scheduled income can enter future cash. Callers must resolve evidence
and identify superseded representations, rather than interpreting every link as
deduplication. The returned flows are not a complete financial forecast.
"""
from .cashflow import Flow
from .contracts import ContractError, iso_date, money


def explicit_flows(events, *, user_id, home_currency, start, end, rates,
                   confirmed_credits=frozenset(), superseded=frozenset()):
    flows, trace = [], []
    identifiers = {e['event_id'] for e in events}
    if len(identifiers) != len(events):
        raise ContractError('Duplicate input event')
    if not set(superseded) <= identifiers or not set(confirmed_credits) <= identifiers:
        raise ContractError('Resolution references unknown event')
    for event in events:
        eid = event['event_id']
        if event['user_id'] != user_id:
            raise ContractError('Cross-user cash event')
        status, direction = event['status'], event['direction']
        if direction not in {'debit', 'credit', 'non_cash'}:
            raise ContractError('Unknown cash direction')
        if status not in {'settled', 'pending', 'scheduled', 'cancelled', 'failed', 'unrealized'}:
            raise ContractError('Unknown cash status')
        reason, day = '', None
        if eid in superseded:
            reason = 'explicitly_superseded_representation'
        elif status in {'cancelled', 'failed', 'unrealized'} or direction == 'non_cash':
            reason = 'excluded_non_cash_or_inactive'
        elif status == 'pending' and direction == 'credit':
            reason = 'unsettled_credit_excluded'
        elif status == 'settled':
            settled = iso_date(event['settlement_date'])
            if settled > start:
                raise ContractError('Settled event after snapshot requires resolution')
            reason = 'already_in_opening_snapshot'
        elif status == 'pending':
            day, reason = start, 'pending_debit_reserved_once'
        else:
            scheduled = iso_date(event['settlement_date'])
            if scheduled < start:
                raise ContractError('Overdue scheduled event requires resolution')
            if direction == 'credit' and eid not in confirmed_credits:
                reason = 'unconfirmed_scheduled_credit_excluded'
            elif scheduled > end:
                reason = 'explicit_event_after_horizon'
            else:
                day, reason = scheduled, 'confirmed_scheduled_cash'
        if day is not None:
            amount = money(event['amount'])  # missing evidence is never zero
            if event['currency'] != home_currency:
                key = (event['settlement_date'], event['currency'], home_currency)
                if key not in rates:
                    raise ContractError('Exact dated directional exchange rate missing')
                amount *= money(rates[key], allow_zero=False)
            signed = -amount if direction == 'debit' else amount
            flows.append(Flow(eid, day, signed, reason))
        trace.append({'event_id': eid, 'included': day is not None, 'reason': reason,
                      'linked_event_id': event['linked_event_id']})
    return tuple(flows), trace
