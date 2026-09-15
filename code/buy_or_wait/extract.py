"""Resumable extraction runner. Produces evidence, never final predictions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .data import Dataset
from .evidence import MODELS, Source
from .gemini import EvidenceBlocked, GeminiExtractor, QuotaBlocked, TransportBlocked, ModelUnavailable


def sources(data: Dataset, *, sample_only: bool = False):
    users = {r['user_id'] for r in data.tables['sample_requests']} if sample_only else set(data.profiles)
    for kind, rows in [('message', data.messages), ('image', data.images)]:
        for sid, row in rows.items():
            if row['user_id'] not in users:
                continue
            event = data.events.get(row['related_event_id'])
            request = data.requests.get(row['request_id'])
            context = {'home_currency': data.profiles[row['user_id']]['home_currency'],
                       'related_event': event, 'related_request': request}
            image = (data.root / 'media' / 'images' / f'{sid}.png').read_bytes() if kind == 'image' else None
            yield Source(sid, kind, row['user_id'], row['request_id'], row['related_event_id'],
                         row.get('sent_at', ''), row.get('message_text', ''), context,
                         hashlib.sha256(image).hexdigest() if image else ''), image


def extract_all(data: Dataset, cache_dir: Path, destination: Path, *, sample_only=False, max_calls=600):
    # Constructor checks credentials before creating files; no fake successful empty run.
    client = GeminiExtractor(cache_dir, max_calls=max_calls, wait_for_minute=True)
    fingerprint=data.fingerprint()
    result = {'status': 'in_progress', 'source_results': {}, 'blocked_sources': {},
              'sample_only': sample_only, 'input_sha256': fingerprint,
              'usage_previous_runs': [], 'cache_hits_previous_runs': 0}
    if destination.exists():
        try:
            previous=json.loads(destination.read_text(encoding='utf-8'))
            previous_hashes=previous.get('input_sha256',{})
            compatible=(previous.get('sample_only')==sample_only and
                        all(previous_hashes.get(k)==v for k,v in fingerprint.items()))
            if compatible:
                result['source_results']=previous.get('source_results',{})
                result['blocked_sources']=previous.get('blocked_sources',{})
                result['usage_previous_runs']=(previous.get('usage_previous_runs',[])+
                                                previous.get('usage_this_run',[]))
                result['cache_hits_previous_runs']=(int(previous.get('cache_hits_previous_runs',0))+
                                                     int(previous.get('cache_hits_this_run',0)))
        except (OSError,json.JSONDecodeError,TypeError):
            # A malformed diagnostic report is ignored; validated cache entries
            # remain independently checked before use.
            pass
    def save():
        destination.parent.mkdir(parents=True, exist_ok=True)
        result['usage_this_run'] = client.usage
        result['cache_hits_this_run'] = client.cache_hits
        pending = destination.with_suffix(destination.suffix + '.tmp')
        pending.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        pending.replace(destination)
    limited_models=set()
    quota_incomplete=False
    try:
        for source, image in sources(data, sample_only=sample_only):
            result['blocked_sources'].pop(source.source_id,None)
            candidates, failures = [], []
            # Pro is approved by name but unavailable on the tested quota and has no
            # published free tier. Do not repeatedly call it or enable paid use.
            approved = (MODELS[1],) if image else MODELS[:2]
            models = tuple(model for model in approved if model not in limited_models)
            if not models:
                quota_incomplete=True
                result['source_results'].setdefault(source.source_id,[])
                result['blocked_sources'][source.source_id]=[
                    {'model':model,'reason':'Model quota unavailable for the remainder of this run'}
                    for model in approved]
                save()
                continue
            for model in models:
                try:
                    candidate = client.extract(source, model, image)
                    candidates.append(candidate)
                    if candidate['status'] == 'candidate_facts':
                        break
                    # Missing source fields can be resolved by other evidence. Keep
                    # facts for cross-source resolution rather than inventing them.
                    if candidate['facts']:
                        break
                except QuotaBlocked as exc:
                    failures.append({'model': model, 'reason': str(exc)})
                    limited_models.add(model)
                    # Quotas are model-specific. A text source may use the already
                    # approved Flash fallback when Lite is limited. If the final
                    # allowed model is also limited, preserve progress and stop.
                    if model != models[-1]:
                        continue
                    quota_incomplete=True
                    break
                except (TransportBlocked, ModelUnavailable) as exc:
                    result['status'] = ('model_unavailable' if isinstance(exc, ModelUnavailable) else 'connection_blocked')
                    result['blocked_sources'][source.source_id] = str(exc)
                    result['source_results'][source.source_id] = candidates
                    save()
                    return result
                except EvidenceBlocked as exc:
                    failures.append({'model': model, 'reason': str(exc)})
            result['source_results'][source.source_id] = candidates
            if not candidates or candidates[-1]['status'] != 'candidate_facts':
                result['blocked_sources'][source.source_id] = failures or 'Evidence requires review'
            # Keep lower-model contradictions; nothing here mutates financial state.
            save()
        result['status'] = ('quota_blocked' if quota_incomplete else
                            'needs_review' if result['blocked_sources'] else 'candidate_facts_ready')
        save()
        return result
    finally:
        client.close()
