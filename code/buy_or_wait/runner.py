"""All-or-nothing prediction runner. Partial runs never replace a valid output."""
import csv,json
from pathlib import Path

from .contracts import ContractError,OUTPUT_COLUMNS
from .decision import decide,DecisionBlocked


def run_predictions(data,resolved_evidence,destination:Path,trace_destination:Path,*,expense_policy):
    rows=[];traces={};blocked={}
    evaluation_ids=[r['request_id'] for r in data.tables['requests']]
    blocking_by_request={}
    for issue in resolved_evidence['issues']:
        if issue.get('blocking') and issue.get('request_id'):
            blocking_by_request.setdefault(issue['request_id'],[]).append(issue)
    for request_id in evaluation_ids:
        if request_id in blocking_by_request:
            blocked[request_id]=f'Blocking evidence: {blocking_by_request[request_id]}'
            continue
        try:
            result=decide(data,resolved_evidence,request_id,expense_policy=expense_policy)
            rows.append(result['row']);traces[request_id]=result['trace']
        except (ContractError,DecisionBlocked) as exc:
            blocked[request_id]=f'{type(exc).__name__}: {exc}'
    trace_destination.parent.mkdir(parents=True,exist_ok=True)
    trace={'status':'blocked' if blocked else 'validated','expense_policy':expense_policy,
           'input_sha256':data.fingerprint(),'rows_completed':len(rows),'blocked':blocked,'traces':traces}
    pending_trace=trace_destination.with_suffix(trace_destination.suffix+'.tmp')
    pending_trace.write_text(json.dumps(trace,indent=2),encoding='utf-8')
    pending_trace.replace(trace_destination)
    if blocked:
        return trace
    if [row['request_id'] for row in rows]!=evaluation_ids or any(tuple(row)!=OUTPUT_COLUMNS for row in rows):
        raise ContractError('Prediction row identity/order/schema failure')
    destination.parent.mkdir(parents=True,exist_ok=True)
    pending=destination.with_suffix(destination.suffix+'.tmp')
    with pending.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=OUTPUT_COLUMNS)
        writer.writeheader();writer.writerows(rows)
    pending.replace(destination)
    return trace
