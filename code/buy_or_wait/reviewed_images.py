"""Ingest explicitly supplied human-reviewed image facts with byte provenance."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .contracts import ContractError
from .evidence import MODELS, Source, validate_extraction

REVIEW_SCHEMA_VERSION = '1'
REVIEW_MODEL = 'manual-local-review'


def _image_source(data, source_id: str) -> Source:
    row = data.images.get(source_id)
    if row is None:
        raise ContractError(f'Review references unknown image source: {source_id!r}')
    path = data.root / 'media' / 'images' / f'{source_id}.png'
    try:
        image = path.read_bytes()
    except OSError as exc:
        raise ContractError(f'Reviewed image file is unavailable: {source_id!r}') from exc
    event = data.events.get(row['related_event_id'])
    request = data.requests.get(row['request_id'])
    return Source(source_id, 'image', row['user_id'], row['request_id'],
                  row['related_event_id'], '', '',
                  {'home_currency': data.profiles[row['user_id']]['home_currency'],
                   'related_event': event, 'related_request': request},
                  hashlib.sha256(image).hexdigest())


def load_reviewed_images(path: Path, data) -> dict:
    """Validate a manual-review manifest against the exact current image bytes.

    The manifest contains source facts only. Request decisions and output fields
    are not accepted. Passing the manifest explicitly is what activates this
    alternate evidence path; it is never discovered or applied automatically.
    """
    try:
        document = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f'Cannot read reviewed-image manifest: {path}') from exc
    if (not isinstance(document, dict) or
            set(document) != {'schema_version', 'review_method', 'reviews'}):
        raise ContractError('Reviewed-image manifest has unexpected fields')
    if document['schema_version'] != REVIEW_SCHEMA_VERSION:
        raise ContractError('Unsupported reviewed-image schema version')
    if not isinstance(document['review_method'], str) or not document['review_method'].strip():
        raise ContractError('Reviewed-image method is required')
    if not isinstance(document['reviews'], list):
        raise ContractError('Reviewed-image reviews must be a list')

    candidates = {}
    for review in document['reviews']:
        if (not isinstance(review, dict) or
                set(review) != {'source_id', 'image_sha256', 'facts', 'unresolved'}):
            raise ContractError('Reviewed-image entry has unexpected fields')
        source_id = review['source_id']
        if not isinstance(source_id, str) or not source_id or source_id in candidates:
            raise ContractError('Reviewed-image source IDs must be unique and non-empty')
        source = _image_source(data, source_id)
        if review['image_sha256'] != source.image_sha256:
            raise ContractError(f'Reviewed image hash differs from source bytes: {source_id}')
        response = {'facts': review['facts'], 'unresolved': review['unresolved']}
        # Reuse the strict fact/schema/date/currency validator. Image quotes are
        # reviewer transcriptions and cannot be mechanically matched to pixels.
        candidate = validate_extraction(source, response, MODELS[1])
        review_body = {'schema_version': REVIEW_SCHEMA_VERSION,
                       'review_method': document['review_method'], **review}
        review_hash = hashlib.sha256(json.dumps(
            review_body, sort_keys=True, ensure_ascii=False,
            separators=(',', ':')).encode()).hexdigest()
        candidates[source_id] = candidate | {
            'model': REVIEW_MODEL,
            'cache_key': f'manual:{review_hash}',
            'review_method': document['review_method'],
            'validation_limit': ('Human-transcribed source facts validated against '
                                 'the exact image SHA-256; no OCR revalidation performed.'),
        }
    return candidates


def merge_reviewed_images(report: dict, reviewed: dict) -> dict:
    """Return a copy with reviewed candidates replacing only unresolved images."""
    merged = copy.deepcopy(report)
    results = merged.get('source_results')
    blocked = merged.get('blocked_sources')
    if not isinstance(results, dict) or not isinstance(blocked, dict):
        raise ContractError('Evidence report has invalid source inventories')
    for source_id, candidate in reviewed.items():
        previous = results.get(source_id, [])
        if previous and previous[-1].get('status') == 'candidate_facts':
            raise ContractError(f'Review cannot override validated model evidence: {source_id}')
        if source_id not in results:
            raise ContractError(f'Review source is outside evidence report: {source_id}')
        results[source_id] = [candidate]
        if candidate['status'] == 'candidate_facts':
            blocked.pop(source_id, None)
        else:
            blocked[source_id] = 'Manual image review requires resolution'
    merged['status'] = 'needs_review' if blocked else 'candidate_facts_ready'
    merged['reviewed_image_sources'] = sorted(reviewed)
    return merged
