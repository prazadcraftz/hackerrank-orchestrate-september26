"""Convert validated evidence facts into explicit, traceable forecast directives."""
import re
from calendar import monthrange
from datetime import date
from decimal import Decimal
from statistics import median

from .contracts import ContractError, iso_date, money

SALARY_WORDS=('salary','payroll','gaji','pay is','first salary')
CONFIRMED_INCOME_WORDS=('invoice payment','pembayaran faktur','confirmed credit','dikonfirmasi untuk')
CATEGORY_WORDS={'rent':('rent','lease'), 'utilities':('utility','utilities','electricity','water bill'),
                'childcare':('childcare','child care'), 'insurance':('insurance',)}


def _next_month_day(after: date, day: int):
    month=after.year*12+after.month-1
    while True:
        year,index=divmod(month,12)
        candidate=date(year,index+1,min(day,monthrange(year,index+1)[1]))
        if candidate>after:
            return candidate
        month+=1


def prepare_evidence(events, facts, *, request_date, home_currency):
    """Apply only visible, typed facts and return mutations plus decision trace.

    This layer deliberately uses source text only to identify salary/category
    semantics already extracted; it never parses a new monetary amount from prose.
    """
    start=iso_date(request_date)
    visible=[]
    for fact in facts:
        observed=fact.get('observed_at','')
        if observed and date.fromisoformat(observed[:10])>start:
            continue
        visible.append(fact)
    result=[dict(e) for e in events]
    by_id={e['event_id']:e for e in result}
    superseded=set()
    confirmed_credit_ids=set()
    trace=[]
    multipliers={}
    salary_directives=[]
    one_time_income=[]
    for fact in visible:
        quote=fact.get('quote','').lower()
        linked=fact.get('related_event_id','')
        if linked and linked not in by_id:
            raise ContractError('Evidence links across user event set')
        if fact['type']=='cancellation' and linked:
            superseded.add(linked)
            trace.append({'source_id':fact['source_id'],'action':'supersede_event','event_id':linked})
        if linked and fact.get('amount'):
            target=by_id[linked]
            # Image amount fills are applied by evidence_resolution after its
            # single-value check. This semantic path is only for a quoted amount
            # in a directly linked message.
            if (not target['amount'] and fact['type']=='amount_fill'
                    and fact.get('source_type')!='image'):
                target['amount']=fact['amount']
                if fact.get('currency'):
                    target['currency']=fact['currency']
                trace.append({'source_id':fact['source_id'],'action':'fill_event_amount',
                              'event_id':linked,'amount':fact['amount']})
            elif fact['type']=='amendment':
                target['amount']=fact['amount']
                if fact.get('currency'):
                    target['currency']=fact['currency']
                trace.append({'source_id':fact['source_id'],'action':'amend_event_amount',
                              'event_id':linked,'amount':fact['amount']})
        if fact['type']=='delay' and linked and fact.get('settlement_date'):
            by_id[linked]['settlement_date']=fact['settlement_date']
            if by_id[linked]['status']=='failed':
                by_id[linked]['status']='scheduled'
            trace.append({'source_id':fact['source_id'],'action':'delay_event','event_id':linked,
                          'settlement_date':fact['settlement_date']})
        if fact['type']=='confirmation' and linked and fact.get('settlement_date'):
            target=by_id[linked]
            target['settlement_date']=fact['settlement_date']
            if target['status']=='failed':
                target['status']='scheduled'
            if target['direction']=='credit' and target['status'] in {'pending','scheduled'}:
                confirmed_credit_ids.add(linked)
            trace.append({'source_id':fact['source_id'],'action':'confirm_event_settlement',
                          'event_id':linked,'settlement_date':fact['settlement_date']})
        salary_meaning=any(word in quote for word in SALARY_WORDS)
        # Directly linked facts already mutate/supersede that exact event above;
        # they must not also create a second user-level salary series.
        salary_directive=(not linked and (fact['type']=='salary_change'
                          or (salary_meaning and fact['type'] in {'confirmation','delay','cancellation'})
                          or (fact['type']=='cancellation' and fact.get('source_type')=='employer'
                              and fact.get('scope')=='user')))
        if salary_directive:
            salary_directives.append({'source_id':fact['source_id'],'type':fact['type'],
                'amount':fact.get('amount',''),'effective_date':fact.get('effective_date',''),
                'settlement_date':fact.get('settlement_date',''),'recurrence':fact.get('recurrence','unknown'),
                'currency':fact.get('currency','') or home_currency,
                'cancelled':fact['type']=='cancellation'})
        elif (fact.get('amount') and fact.get('settlement_date') and
              any(word in quote for word in CONFIRMED_INCOME_WORDS) and
              fact['type'] in {'amount_fill','confirmation'}):
            one_time_income.append(fact)
        if fact['type']=='amendment':
            percentages=re.findall(r'(?<!\d)(\d+(?:\.\d+)?)\s*%',fact.get('quote',''))
            categories=[category for category,words in CATEGORY_WORDS.items() if any(w in quote for w in words)]
            if len(percentages)==1 and len(categories)==1:
                multipliers[categories[0]]=Decimal('1')+money(percentages[0])/Decimal('100')
                trace.append({'source_id':fact['source_id'],'action':'series_multiplier',
                              'category':categories[0],'multiplier':str(multipliers[categories[0]])})
    directive=None
    if salary_directives:
        # Newest visible source wins after explicit cancellation. Multiple source
        # timestamps are already represented by input order; conflicting amounts
        # on one request stay traceable rather than averaged.
        directive=salary_directives[-1]
        replacement=next((d for d in reversed(salary_directives) if not d['cancelled'] and d['amount']),None)
        cancelled=any(d['cancelled'] for d in salary_directives)
        directive=replacement or next((d for d in reversed(salary_directives) if d['cancelled']),directive)
        directive=directive|{'replace_existing':cancelled and replacement is not None}
    followup={}
    suppress_historical_salary=False
    if directive and directive['cancelled']:
        suppress_historical_salary=True
        superseded.update(e['event_id'] for e in result if e['status']=='scheduled'
                          and e['direction']=='credit' and e['category']=='salary')
        trace.append({'source_id':directive['source_id'],'action':'cancel_future_salary'})
    elif directive and (directive['amount'] or directive['settlement_date']):
        history=[e for e in result if e['status']=='settled' and e['direction']=='credit'
                 and e['category']=='salary' and e['amount']]
        ordinary_events=[e for e in history if not any(x in e['description'].lower()
                         for x in ('bonus','commission','prize','arrears','project','invoice','platform'))]
        ordinary_events=[e for e in ordinary_events if e['currency']==directive['currency']]
        ordinary=[money(e['amount']) for e in ordinary_events]
        baseline=Decimal(str(median(ordinary))) if ordinary else None
        scheduled=sorted((e for e in result if e['status']=='scheduled' and e['direction']=='credit'
                          and e['category']=='salary'),key=lambda e:e['settlement_date'])
        amount=money(directive['amount']) if directive['amount'] else baseline
        if amount is None:
            raise ContractError('Salary timing evidence has no resolved amount basis')
        if directive['settlement_date']:
            first=iso_date(directive['settlement_date'])
        elif directive['effective_date']:
            first=iso_date(directive['effective_date'])
        elif scheduled:
            first=iso_date(scheduled[0]['settlement_date'])
        elif ordinary_events:
            first=_next_month_day(start,iso_date(ordinary_events[-1]['settlement_date']).day)
        else:
            raise ContractError('Salary evidence has no supported first settlement date')
        if scheduled:
            target=scheduled[0]
            target['amount'],target['settlement_date'],target['currency']=str(amount),first.isoformat(),directive['currency']
        else:
            identity=f"evidence:{directive['source_id']}:salary"
            target={'event_id':identity,'user_id':result[0]['user_id'],'event_type':'income',
                    'description':'Next confirmed salary','category':'salary','direction':'credit',
                    'amount':str(amount),'currency':directive['currency'],'event_date':first.isoformat(),
                    'settlement_date':first.isoformat(),'status':'scheduled','linked_event_id':'',
                    'flexibility':'fixed','minimum_allowed_amount':''}
            result.append(target)
        followup[target['event_id']]=(baseline if directive['recurrence']=='temporary' and baseline is not None else amount)
        trace.append({'source_id':directive['source_id'],'action':'set_next_salary','event_id':target['event_id'],
                      'amount':str(amount),'settlement_date':first.isoformat(),
                      'followup_amount':str(followup[target['event_id']])})
    for fact in one_time_income:
        identity=f"evidence:{fact['source_id']}:income"
        if identity in {e['event_id'] for e in result}:
            raise ContractError('Duplicate evidence income identity')
        result.append({'event_id':identity,'user_id':result[0]['user_id'],'event_type':'income',
            'description':'Confirmed one-time income','category':'other_income','direction':'credit',
            'amount':fact['amount'],'currency':fact.get('currency') or home_currency,
            'event_date':fact['settlement_date'],'settlement_date':fact['settlement_date'],
            'status':'scheduled','linked_event_id':'','flexibility':'fixed','minimum_allowed_amount':''})
        trace.append({'source_id':fact['source_id'],'action':'add_confirmed_one_time_income',
                      'event_id':identity,'amount':fact['amount'],'settlement_date':fact['settlement_date']})
    return {'events':result,'superseded':superseded,'confirmed_credit_ids':confirmed_credit_ids,
            'salary_followup':followup,
            'suppress_historical_salary':suppress_historical_salary,
            'expense_multipliers':multipliers,'trace':trace}
