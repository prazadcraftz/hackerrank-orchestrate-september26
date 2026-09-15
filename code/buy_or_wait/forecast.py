"""Build an auditable 90-date forecast from already resolved event facts."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from .cashflow import CashState, Flow
from .cash_state import explicit_flows
from .contracts import ContractError, iso_date, money
from .recurrence import infer_cadence, occurrence_dates, expense_estimate, Cadence

VARIABLE_EXPENSES = {'groceries', 'transport', 'dining', 'shopping', 'utilities',
                     'healthcare', 'entertainment'}
NONREGULAR_INCOME_WORDS = {'final', 'prorated', 'bonus', 'commission', 'prize',
                           'refund', 'arrears', 'project', 'invoice', 'marketplace',
                           'platform', 'contract', 'app earnings', 'freelance',
                           'independent', 'retainer', 'temporary assignment',
                           'seasonal', 'peak-season', 'previous employer'}


def is_regular_salary(description: str) -> bool:
    value = description.lower()
    return not any(word in value for word in NONREGULAR_INCOME_WORDS)


def _convert(amount, currency, home, day, rates):
    if currency == home:
        return amount
    key = (day.isoformat(), currency, home)
    if key not in rates:
        raise ContractError('Exact dated directional exchange rate missing for projection')
    return amount * money(rates[key], allow_zero=False)


def _with_amounts(events, overrides):
    unknown = set(overrides) - {e['event_id'] for e in events}
    if unknown:
        raise ContractError('Amount override references unknown event')
    result = []
    for event in events:
        if event['event_id'] in overrides:
            if event['amount']:
                raise ContractError('Amount override may fill blanks only')
            event = event | {'amount': str(money(overrides[event['event_id']]))}
        result.append(event)
    return result


def build_forecast(events, profile, request, rates, *, amount_overrides=None,
                   confirmed_credit_ids=frozenset(), superseded=frozenset(),
                   horizon_dates=90, intraday='debits_first', expense_policy='maximum',
                   salary_followup=None, expense_multipliers=None,
                   suppress_historical_salary=False):
    """Return state, series trace and blockers without using sample answers.

    A supplied `Next confirmed salary` is explicit and establishes a monthly
    forward payroll anchor unless superseded. Other projected income needs at
    least three supported settled observations. Variable expense amount policy
    is explicit and applies to the six most recent comparable observations.
    """
    amount_overrides = amount_overrides or {}
    salary_followup = salary_followup or {}
    expense_multipliers = expense_multipliers or {}
    events = _with_amounts(events, amount_overrides)
    start = iso_date(request['request_date'])
    end = start + timedelta(days=horizon_dates - 1)
    home = profile['home_currency']
    scheduled_salary = {e['event_id'] for e in events if e['status']=='scheduled'
                        and e['direction']=='credit' and e['category']=='salary'
                        and e['description']=='Next confirmed salary'}
    confirmed = set(confirmed_credit_ids) | scheduled_salary
    explicit, event_trace = explicit_flows(events, user_id=request['user_id'],
        home_currency=home, start=start, end=end, rates=rates,
        confirmed_credits=confirmed, superseded=superseded)
    flows = list(explicit)
    explicit_occurrences = {(e['category'], e['direction'], iso_date(e['settlement_date']))
                            for e in events if e['status'] in {'pending','scheduled'}
                            and e['settlement_date'] and start <= iso_date(e['settlement_date']) <= end}
    series_trace, blockers = [], []

    # Debit series are category-level for variable spending, and description-level
    # for fixed bills/subscriptions so separate commitments cannot be collapsed.
    debit_groups = defaultdict(list)
    for e in events:
        if (e['status']=='settled' and e['direction']=='debit' and e['settlement_date'] < request['request_date']
                and e['event_type'] in {'expense','subscription','debt_payment'}):
            key = ((e['category'], '*', e['currency']) if e['category'] in VARIABLE_EXPENSES
                   else (e['category'], e['description'], e['currency']))
            debit_groups[key].append(e)
    for (category, description, currency), history in sorted(debit_groups.items()):
        history.sort(key=lambda e:e['settlement_date'])
        cadence = infer_cadence([iso_date(e['settlement_date']) for e in history])
        usable = [e for e in history if e['amount']]
        if cadence is None or len(usable) < 3:
            continue
        sample = usable[-6:]
        values = [money(e['amount']) for e in sample]
        amount = (expense_estimate(values, policy=expense_policy)
                  if len(set(values)) > 1 else values[-1])
        amount *= expense_multipliers.get(category,Decimal('1'))
        anchor = history[-1]
        projected = []
        for day in occurrence_dates(cadence, after=iso_date(anchor['settlement_date']), through=end):
            if day < start or (category, 'debit', day) in explicit_occurrences:
                continue
            identity = f"projected:{anchor['event_id']}:{day.isoformat()}"
            flows.append(Flow(identity, day, -_convert(amount, currency, home, day, rates),
                              'supported_recurring_expense'))
            projected.append(day.isoformat())
        series_trace.append({'kind':'expense','category':category,'description':description,
            'anchor_event_id':anchor['event_id'],'cadence':cadence.kind,'interval':cadence.interval,
            'amount':str(amount),'observation_ids':[e['event_id'] for e in sample],
            'projected_dates':projected})

    # A scheduled next salary is an explicit regular-pay anchor. Projecting from
    # it is necessary for a 90-day horizon even when the preceding salary was a
    # prorated first payment. Messages may supersede/alter it before this stage.
    for scheduled in sorted((e for e in events if e['event_id'] in scheduled_salary and e['event_id'] not in superseded),
                            key=lambda e:e['settlement_date']):
        if not scheduled['amount']:
            blockers.append({'event_id':scheduled['event_id'],'reason':'confirmed salary amount unresolved'})
            continue
        anchor_day = iso_date(scheduled['settlement_date'])
        cadence = Cadence('monthly',1,anchor_day,1,1)
        projected=[]
        for day in occurrence_dates(cadence,after=anchor_day,through=end):
            if ('salary','credit',day) in explicit_occurrences:
                continue
            identity=f"projected:{scheduled['event_id']}:{day.isoformat()}"
            followup=money(salary_followup.get(scheduled['event_id'],scheduled['amount']))
            flows.append(Flow(identity, day, _convert(followup, scheduled['currency'], home, day, rates),
                              'confirmed_regular_salary'))
            projected.append(day.isoformat())
        series_trace.append({'kind':'income','category':'salary','description':'Next confirmed salary',
            'anchor_event_id':scheduled['event_id'],'cadence':'monthly','interval':1,
            'amount':str(salary_followup.get(scheduled['event_id'],scheduled['amount'])),
            'first_amount':scheduled['amount'],'observation_ids':[scheduled['event_id']],
            'projected_dates':projected})

    # Other salary series require stable repeated history and recent activity.
    salary_groups=defaultdict(list)
    for e in events:
        if (not suppress_historical_salary and e['status']=='settled' and e['direction']=='credit' and e['category']=='salary'
                and e['settlement_date'] < request['request_date'] and is_regular_salary(e['description'])):
            salary_groups[e['description']].append(e)
    final_dates=[iso_date(e['settlement_date']) for e in events if e['status']=='settled'
                 and e['direction']=='credit' and e['category']=='salary' and 'final' in e['description'].lower()]
    for description,history in sorted(salary_groups.items()):
        history.sort(key=lambda e:e['settlement_date'])
        last=history[-1]
        last_day=iso_date(last['settlement_date'])
        if any(d >= last_day for d in final_dates) or (start-last_day).days > 45:
            continue
        cadence=infer_cadence([iso_date(e['settlement_date']) for e in history])
        usable=[e for e in history[-6:] if e['amount']]
        if cadence is None or len(usable)<3:
            continue
        # When an explicit next salary exists, the matched projection dates are
        # already covered by the scheduled-anchor series; avoid double income.
        if scheduled_salary:
            continue
        amount=min(money(e['amount']) for e in usable)
        projected=[]
        for day in occurrence_dates(cadence,after=last_day,through=end):
            if day < start or ('salary','credit',day) in explicit_occurrences:
                continue
            identity=f"projected:{last['event_id']}:{day.isoformat()}"
            flows.append(Flow(identity, day, _convert(amount, last['currency'], home, day, rates),
                              'supported_conservative_salary'))
            projected.append(day.isoformat())
        series_trace.append({'kind':'income','category':'salary','description':description,
            'anchor_event_id':last['event_id'],'cadence':cadence.kind,'interval':cadence.interval,
            'amount':str(amount),'observation_ids':[e['event_id'] for e in usable],
            'projected_dates':projected})
    state=CashState(start,end,money(profile['current_available_balance']),
                    money(profile['minimum_balance_to_keep']),tuple(flows),intraday)
    return {'state':state,'event_trace':event_trace,'series_trace':series_trace,'blockers':blockers,
            'policy':{'horizon_dates':horizon_dates,'intraday':intraday,'expense_policy':expense_policy}}
