"""Integrated deterministic decision assembly and independent validation."""
from decimal import Decimal

from .amendments import prepare_evidence
from .cashflow import replay
from .changes import apply_actions, legal_actions, spending_change_candidates
from .contracts import ContractError, OUTPUT_COLUMNS, iso_date, money, static_errors
from .forecast import build_forecast
from .plans import no_change_candidates, rank


class DecisionBlocked(RuntimeError):
    pass


def installment_eligible(option, profile):
    """All supplied installment offers are monthly (28/30/31-day frequency)."""
    frequency=int(option['payment_frequency_days'])
    if frequency not in {28,30,31}:
        raise DecisionBlocked('Non-monthly installment duration is unresolved')
    return int(option['number_of_payments']) <= int(profile['max_installment_months'])


def _plan(payments):
    return '|'.join(f'{day.isoformat()}:{amount}' for day,amount in payments) if payments else 'none'


def decide(data, resolved_evidence, request_id, *, expense_policy='maximum'):
    request=data.requests[request_id]
    profile=data.profiles[request['user_id']]
    user_events=data.events_by_user[request['user_id']]
    event_ids={e['event_id'] for e in user_events}
    overrides={k:v for k,v in resolved_evidence['amount_overrides'].items() if k in event_ids}
    prepared=prepare_evidence(user_events,resolved_evidence['facts_by_user'].get(request['user_id'],[]),
                              request_date=request['request_date'],home_currency=profile['home_currency'])
    rates={(r['rate_date'],r['from_currency'],r['to_currency']):r['rate'] for r in data.tables['exchange_rates']}
    built=build_forecast(prepared['events'],profile,request,rates,amount_overrides=overrides,
        confirmed_credit_ids=prepared['confirmed_credit_ids'],superseded=prepared['superseded'],
        salary_followup=prepared['salary_followup'],
        suppress_historical_salary=prepared['suppress_historical_salary'],
        expense_multipliers=prepared['expense_multipliers'],expense_policy=expense_policy)
    if built['blockers']:
        raise DecisionBlocked(f'Forecast facts unresolved: {built["blockers"]}')
    baseline=no_change_candidates(built['state'],request,profile,data.options_by_request[request_id],
                                  installment_eligible=installment_eligible)
    changed=spending_change_candidates(built['state'],request,profile,data.options_by_request[request_id],
        built['series_trace'],prepared['events'],installment_eligible=installment_eligible)
    deadline=iso_date(request['desired_completion_date'])
    candidates=sorted(baseline['candidates']+changed,key=lambda c:rank(c,deadline))
    selected=candidates[0] if candidates else None
    safe=baseline['capacity']['safe_today']
    earliest=baseline['capacity']['earliest_full']
    currency=profile['home_currency']
    requested=money(request['requested_amount'])
    if selected is None:
        status,method,plan,changes='not_affordable','not_recommended','none','none'
        explanation=(f'No eligible plan completes {currency} {requested} by {request["desired_completion_date"]} '
                     f'while preserving the {currency} {money(profile["minimum_balance_to_keep"])} minimum.')
    else:
        method=selected.method
        changes='|'.join(selected.changes) if selected.changes else 'none'
        plan=_plan(selected.payments)
        if method=='full_payment' and not selected.changes:
            status='affordable_now'
            explanation=(f'Pay {currency} {requested} in full on {request["request_date"]}; the validated '
                         f'90-date forecast preserves the {currency} {money(profile["minimum_balance_to_keep"])} minimum.')
        elif method=='wait':
            status='affordable_later'
            explanation=(f'Wait until {selected.payments[0][0].isoformat()} to pay {currency} {requested} in full '
                         f'while preserving the {currency} {money(profile["minimum_balance_to_keep"])} minimum.')
        else:
            status='affordable_with_plan'
            detail=(f'{len(selected.payments)} payments' if method=='installments' else
                    'two payments' if method=='partial_payment' else 'permitted spending changes')
            explanation=(f'Use {detail} to complete {currency} {requested} by '
                         f'{selected.payments[-1][0].isoformat()} while preserving the '
                         f'{currency} {money(profile["minimum_balance_to_keep"])} minimum.')
    row=dict(zip(OUTPUT_COLUMNS,(request_id,str(safe),status,method,plan,
        earliest.isoformat() if earliest else '',changes,explanation)))
    static=static_errors(row,request,profile,data.options_by_request[request_id],data.events)
    if static:
        raise DecisionBlocked(f'Serialized decision failed contract: {static}')
    # Replay again after serialization selection. Spending actions change only the
    # series they legally target; all other flows remain frozen.
    replay_state=built['state']
    if selected and selected.changes:
        action_map={a['serialized']:a for group in legal_actions(built['series_trace'],prepared['events'],profile) for a in group}
        actions=[action_map[value] for value in selected.changes]
        replay_state,_=apply_actions(replay_state,actions,built['series_trace'])
    if selected and not replay(replay_state,list(selected.payments))['safe']:
        raise DecisionBlocked('Independent final replay rejected selected plan')
    return {'row':row,'trace':{'policy':built['policy'],'evidence_actions':prepared['trace'],
        'series':built['series_trace'],'capacity':{k:(str(v) if not isinstance(v,dict) else
        {d.isoformat():str(a) for d,a in v.items()}) for k,v in baseline['capacity'].items()},
        'rejected':baseline['rejected'],'selected':repr(selected)}}
