"""Exhaustive legal spending-change search over resolved recurring series."""
from dataclasses import replace
from decimal import Decimal
from itertools import combinations, product

from .cashflow import CashState, replay
from .contracts import ContractError, iso_date, money, option_schedule
from .plans import Candidate, rank


def legal_actions(series_trace, events, profile):
    protected=set(profile['expense_categories_to_protect'].split('|'))
    reducible=set(profile['expense_categories_user_is_willing_to_reduce'].split('|'))
    stoppable=set(profile['expense_categories_user_is_willing_to_stop'].split('|'))
    by_id={e['event_id']:e for e in events}
    groups=[]
    seen=set()
    for series in series_trace:
        if series['kind']!='expense' or not series['projected_dates']:
            continue
        eid=series['anchor_event_id']
        if eid in seen:
            continue
        seen.add(eid)
        event=by_id[eid]
        category=event['category']
        if category in protected or event['direction']!='debit':
            continue
        choices=[]
        if event['flexibility'] in {'stoppable','reducible_or_stoppable'} and category in stoppable:
            choices.append({'kind':'stop','event_id':eid,'value':Decimal('0'),
                            'serialized':f'stop:{eid}'})
        if (event['flexibility'] in {'reducible','reducible_or_stoppable'} and category in reducible
                and event['minimum_allowed_amount']):
            floor=money(event['minimum_allowed_amount'])
            original=money(series['amount'])
            if floor < original:
                choices.append({'kind':'reduce_to','event_id':eid,'value':floor,
                                'serialized':f'reduce_to:{eid}:{floor}'})
        if choices:
            groups.append(choices)
    return groups


def apply_actions(state: CashState, actions, series_trace):
    series={s['anchor_event_id']:s for s in series_trace if s['kind']=='expense'}
    flows=[]
    savings=Decimal('0')
    for flow in state.flows:
        action=next((a for a in actions if flow.identity.startswith(f"projected:{a['event_id']}:") ),None)
        if action is None:
            flows.append(flow)
            continue
        if action['kind']=='stop':
            savings += -flow.amount
            continue
        original=money(series[action['event_id']]['amount'])
        if original <= 0:
            raise ContractError('Cannot scale a zero recurring expense')
        new_amount=(-flow.amount)*(action['value']/original)
        savings += (-flow.amount)-new_amount
        flows.append(replace(flow,amount=-new_amount,reason='permitted_recurring_reduction'))
    return replace(state,flows=tuple(flows)),savings


def spending_change_candidates(state, request, profile, options, series_trace, events, *, installment_eligible):
    """Generate replay-safe full/installment plans for all action sets up to three.

    It never changes amount_safe_to_pay or earliest-full capacity; callers retain
    those from the unmodified baseline. Savings start only at projected recurring
    occurrences, so an action cannot create request-day cash.
    """
    requested=money(request['requested_amount'],allow_zero=False)
    deadline=iso_date(request['desired_completion_date'])
    accepted=set(profile['payment_methods_user_will_consider'].split('|'))
    action_groups=legal_actions(series_trace,events,profile)
    valid=[]
    schedules=[]
    if 'full_payment' in accepted:
        schedules.append(('full_payment',((state.start,requested),),''))
    if 'installments' in accepted and profile['max_installment_months']:
        for option in options:
            if option['request_id']!=request['request_id']:
                raise ContractError('Cross-request payment option')
            if option['payment_method']=='installments' and installment_eligible(option,profile):
                schedule=tuple(option_schedule(option))
                if sum((a for _,a in schedule),Decimal('0'))!=money(option['total_payable_amount']):
                    raise ContractError('Inconsistent installment schedule')
                schedules.append(('installments',schedule,option['payment_option_id']))
    for size in range(1,min(3,len(action_groups))+1):
        for selected_groups in combinations(action_groups,size):
            for actions in product(*selected_groups):
                changed,savings=apply_actions(state,actions,series_trace)
                changes=tuple(sorted(a['serialized'] for a in actions))
                for method,schedule,option_id in schedules:
                    if any(d>min(deadline,state.end) for d,_ in schedule):
                        continue
                    if replay(changed,list(schedule))['safe']:
                        valid.append(Candidate(method,schedule,option_id,changes,savings))
    # Same plan/action can arise only once today, but deduplicate defensively.
    unique={(c.method,c.payments,c.option_id,c.changes):c for c in valid}
    return sorted(unique.values(),key=lambda c:rank(c,deadline))
