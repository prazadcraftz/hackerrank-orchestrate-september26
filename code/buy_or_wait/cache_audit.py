"""Read-only coverage audit for versioned Gemini evidence caches."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .contracts import ContractError
from .evidence import MODELS, cache_key, validate_extraction
from .extract import sources


def _cached_candidate(source, cache_dir: Path):
    allowed=(MODELS[1],) if source.kind=='image' else MODELS[:2]
    attempts=[]
    for model in allowed:
        path=cache_dir/f'{cache_key(source,model)}.json'
        if not path.exists():
            attempts.append({'model':model,'state':'missing'})
            continue
        try:
            raw=json.loads(path.read_text(encoding='utf-8'))
            candidate=validate_extraction(source,raw,model)
        except (OSError,json.JSONDecodeError,ContractError):
            attempts.append({'model':model,'state':'invalid'})
            continue
        attempts.append({'model':model,'state':'valid','status':candidate['status']})
        return candidate,attempts
    return None,attempts


def audit_source_cache(source, cache_dir: Path) -> dict:
    """Find the first currently valid approved cache without changing files."""
    candidate,attempts=_cached_candidate(source,cache_dir)
    if candidate:
        return {'source_id':source.source_id,'kind':source.kind,'ready':True,
                'model':candidate['model'],'candidate_status':candidate['status'],'attempts':attempts}
    return {'source_id':source.source_id,'kind':source.kind,'ready':False,
            'model':'','candidate_status':'','attempts':attempts}


def audit_cache(data, cache_dir: Path, *, sample_only=False) -> dict:
    rows=[audit_source_cache(source,cache_dir) for source,_ in sources(data,sample_only=sample_only)]
    ready=[row for row in rows if row['ready']]
    return {'sources_total':len(rows),'ready':len(ready),'requires_call':len(rows)-len(ready),
            'ready_by_model':dict(sorted(Counter(row['model'] for row in ready).items())),
            'requires_call_by_kind':dict(sorted(Counter(row['kind'] for row in rows if not row['ready']).items())),
            'sources_requiring_call':[row for row in rows if not row['ready']]}


def consolidate_cache(data, cache_dir: Path, destination: Path, *, sample_only=False) -> dict:
    """Write a diagnostic evidence report using validated local caches only."""
    result={'status':'in_progress','source_results':{},'blocked_sources':{},
            'sample_only':sample_only,'input_sha256':data.fingerprint(),
            'usage_previous_runs':[],'cache_hits_previous_runs':0,
            'usage_this_run':[],'cache_hits_this_run':0}
    for source,_ in sources(data,sample_only=sample_only):
        candidate,_=_cached_candidate(source,cache_dir)
        result['source_results'][source.source_id]=[candidate] if candidate else []
        if candidate is None:
            result['blocked_sources'][source.source_id]='No currently valid local cache'
        elif candidate['status']!='candidate_facts':
            result['blocked_sources'][source.source_id]='Evidence requires review'
        else:
            result['cache_hits_this_run']+=1
    result['status']='needs_review' if result['blocked_sources'] else 'candidate_facts_ready'
    destination.parent.mkdir(parents=True,exist_ok=True)
    pending=destination.with_suffix(destination.suffix+'.tmp')
    pending.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    pending.replace(destination)
    return result
