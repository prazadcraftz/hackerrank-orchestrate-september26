"""Deterministically resolve model candidate facts into bounded state inputs."""
import json

from .contracts import ContractError, money


def load_report(path, data):
    report=json.loads(path.read_text(encoding='utf-8'))
    if report.get('status') not in {'candidate_facts_ready','needs_review'}:
        raise ContractError('Evidence extraction report is incomplete')
    expected=data.fingerprint()
    actual=report.get('input_sha256')
    # Older reports included the blank output template; compare every evidence
    # input while allowing that one legacy extra key.
    if not isinstance(actual,dict) or any(actual.get(k)!=v for k,v in expected.items()):
        raise ContractError('Evidence report does not match dataset inputs')
    return report


def resolve_candidates(report, data):
    """Return safe automatic facts and explicit issues; never produce a decision.

    Only image facts may fill blank event amounts automatically. Message amounts
    can amend state only in the later semantic layer because linked context is not
    proof that a message stated the value. Multiple plausible amount fills block.
    """
    overrides, issues, facts_by_user = {}, [], {}
    results=report.get('source_results',{})
    sources={**data.messages,**data.images}
    request_by_user={row['user_id']:row for row in getattr(data,'requests',{}).values()}
    for source_id,row in sources.items():
        candidates=results.get(source_id)
        if not candidates:
            event=data.events.get(row.get('related_event_id',''))
            request_id=row.get('request_id','')
            request=getattr(data,'requests',{}).get(request_id) or request_by_user.get(row['user_id'])
            request_id=request['request_id'] if request else request_id
            visible=True
            if source_id in data.messages and request and row.get('sent_at'):
                visible=row['sent_at'][:10] <= request['request_date']
            missing_message=(source_id in data.messages and visible and bool(request_id))
            missing_future_amount=(source_id in data.images and event is not None and not event['amount']
                                   and event['status'] in {'pending','scheduled'})
            blocking=missing_message or missing_future_amount
            issues.append({'source_id':source_id,'request_id':request_id,
                           'blocking':blocking,'reason':'source not extracted'})
            continue
        candidate=candidates[-1]
        if candidate.get('source',{}).get('source_id')!=source_id:
            raise ContractError('Evidence source identity mismatch')
        facts=candidate.get('facts',[])
        facts_by_user.setdefault(row['user_id'],[]).extend(
            {'source_id':source_id,'request_id':row.get('request_id',''),
             'related_event_id':row.get('related_event_id',''),
             'source_type':row.get('source_type','image'),
             'observed_at':candidate.get('source',{}).get('observed_at',''),**fact} for fact in facts)
        event_id=row.get('related_event_id','')
        if source_id in data.images and event_id and not data.events[event_id]['amount']:
            values={money(f['amount']) for f in facts if f.get('type')=='amount_fill'
                    and f.get('scope')=='event' and f.get('amount')}
            if len(values)==1:
                overrides[event_id]=values.pop()
            else:
                issues.append({'source_id':source_id,'request_id':row.get('request_id',''),
                               'event_id':event_id,'blocking':data.events[event_id]['status'] in {'pending','scheduled'},
                               'reason':'blank event amount has zero or multiple candidate fills'})
        for item in candidate.get('unresolved',[]):
            issues.append({'source_id':source_id,'request_id':row.get('request_id',''),
                           'blocking':False,'reason':item})
    return {'amount_overrides':overrides,'facts_by_user':facts_by_user,'issues':issues}
