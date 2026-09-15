"""Bounded Gemini REST extraction with persistent local quota and usage records.

This quota ledger covers this checkout, not other callers in the Google project.
On quota exhaustion the caller must save progress and resume; no key rotation.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .contracts import ContractError
from .evidence import INSTRUCTION, MODELS, SCHEMA, Source, cache_key, validate_extraction

# Conservative local budgets retained from the user's original configuration.
# NOT a statement of these replacement models' actual project quotas. Server
# 429 responses always prevail; this ledger cannot observe other project clients.
CAPS = {'gemini-3.5-flash-lite': (15, 250_000, 1000),
        'gemini-3.6-flash': (10, 250_000, 250),
        'gemini-3.1-pro-preview': (5, 250_000, 100)}


class EvidenceBlocked(RuntimeError):
    pass


class QuotaBlocked(EvidenceBlocked):
    pass


class TransportBlocked(EvidenceBlocked):
    pass


class ModelUnavailable(EvidenceBlocked):
    pass


def pacific_day(now: datetime) -> str:
    try:
        return now.astimezone(ZoneInfo('America/Los_Angeles')).date().isoformat()
    except ZoneInfoNotFoundError as exc:
        raise EvidenceBlocked('Timezone database unavailable; install tzdata before live extraction.') from exc


class GeminiExtractor:
    def __init__(self, cache_dir: Path, *, max_calls: int = 600, transport=None,
                 clock=None, day_key=None, caps=None, wait_for_minute=False):
        self.key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if not self.key and transport is None:
            raise EvidenceBlocked('Set GEMINI_API_KEY or GOOGLE_API_KEY locally before live extraction.')
        if max_calls < 1:
            raise ValueError('max_calls must be positive')
        self.root = cache_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'quota.sqlite', timeout=30)
        self.db.execute('CREATE TABLE IF NOT EXISTS calls (model TEXT, time REAL, day TEXT, tokens INTEGER, operation TEXT)')
        self.db.commit()
        self.transport = transport or self._http
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.day_key = day_key or pacific_day
        self.caps = caps or CAPS
        self.max_calls = max_calls
        self.calls = 0
        self.usage = []
        self.cache_hits = 0
        self.wait_for_minute = wait_for_minute

    def close(self):
        self.db.close()

    def _reserve(self, model: str, tokens: int, operation: str):
        if self.calls >= self.max_calls:
            raise QuotaBlocked('Run call budget exhausted. Resume from cache with an explicit new budget.')
        now = self.clock()
        day = self.day_key(now)
        rpm, tpm, rpd = self.caps[model]
        self.db.execute('BEGIN IMMEDIATE')
        try:
            recent = self.db.execute('SELECT COUNT(*), COALESCE(SUM(tokens),0) FROM calls WHERE model=? AND time>?',
                                     (model, now.timestamp() - 60)).fetchone()
            daily = self.db.execute('SELECT COUNT(*) FROM calls WHERE model=? AND day=?', (model, day)).fetchone()[0]
            if daily >= rpd or tokens > tpm:
                raise QuotaBlocked(f'Local quota reached for {model}; preserve progress and resume after reset.')
            if recent[0] >= rpm or recent[1] + tokens > tpm:
                if not self.wait_for_minute:
                    raise QuotaBlocked(f'Local quota reached for {model}; preserve progress and resume after reset.')
                oldest = self.db.execute('SELECT MIN(time) FROM calls WHERE model=? AND time>?', (model, now.timestamp() - 60)).fetchone()[0]
                self.db.rollback()
                time.sleep(min(60, max(1, oldest + 60.1 - now.timestamp())))
                return self._reserve(model, tokens, operation)
            self.db.execute('INSERT INTO calls VALUES (?,?,?,?,?)', (model, now.timestamp(), day, tokens, operation))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.calls += 1

    def _http(self, model, operation, body):
        request = Request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:{operation}',
                          data=json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json', 'x-goog-api-key': self.key}, method='POST')
        try:
            with urlopen(request, timeout=45) as response:
                return json.load(response)
        except HTTPError as exc:
            # Never include request headers, URL query credentials, or arbitrary provider error bodies.
            if exc.code == 429:
                raise QuotaBlocked('Gemini project quota/rate limit returned HTTP 429; retry later.') from None
            if exc.code == 404:
                raise ModelUnavailable(f'Gemini model {model} is unavailable for this operation/key (HTTP 404). Stop and verify model access.') from None
            raise EvidenceBlocked(f'Gemini returned HTTP {exc.code}; extraction remains unresolved.') from None
        except (URLError, TimeoutError, json.JSONDecodeError):
            raise TransportBlocked('Gemini connection unavailable; stop the run before further model attempts.') from None

    def _call(self, model, operation, body, tokens=0):
        self._reserve(model, tokens, operation)
        record = {'model': model, 'operation': operation, 'time': self.clock().isoformat(),
                  'status': 'started', 'reserved_input_tokens': tokens}
        try:
            response = self.transport(model, operation, body)
            record['status'] = 'ok'
            record['usage'] = response.get('usageMetadata', {})
            return response
        except Exception:
            record['status'] = 'failed'
            raise
        finally:
            self.usage.append(record)
            with (self.root / 'usage.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
                stream.write(json.dumps(record) + '\n')

    def extract(self, source: Source, model: str, image_bytes: bytes | None = None) -> dict:
        if model not in MODELS:
            raise ContractError('Unapproved model')
        if source.kind == 'image' and (image_bytes is None or hashlib.sha256(image_bytes).hexdigest() != source.image_sha256):
            raise ContractError('Image content/hash mismatch')
        key = cache_key(source, model)
        path = self.root / f'{key}.json'
        if path.exists():
            try:
                response = json.loads(path.read_text(encoding='utf-8'))
                validated = validate_extraction(source, response, model)
            except (json.JSONDecodeError, ContractError) as exc:
                # Quarantine stale prompt/schema output for diagnosis, then let
                # this approved model regenerate it. Leaving an invalid file at
                # the active key would force every resumed run to waste fallback
                # quota without ever giving the primary model another chance.
                quarantine=path.with_name(f'{key}.invalid-{time.time_ns()}.json')
                path.replace(quarantine)
            else:
                self.cache_hits += 1
                return validated
        # A validator hardening/repair may make a preserved diagnostic acceptable
        # under the current rules. Revalidate newest-first and copy, never relabel,
        # the raw facts into the active versioned cache without another API call.
        diagnostics=sorted(self.root.glob(f'{key}.invalid-*.json'),
                           key=lambda item:item.stat().st_mtime,reverse=True)
        for diagnostic in diagnostics:
            try:
                response=json.loads(diagnostic.read_text(encoding='utf-8'))
                validated=validate_extraction(source,response,model)
            except (OSError,json.JSONDecodeError,ContractError):
                continue
            temporary=path.with_suffix('.tmp')
            temporary.write_text(json.dumps(response,ensure_ascii=False,indent=2),encoding='utf-8')
            temporary.replace(path)
            self.cache_hits += 1
            return validated
        parts = [{'text': json.dumps(source.payload(), ensure_ascii=False)}]
        if image_bytes is not None:
            parts.append({'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(image_bytes).decode()}})
        # Count the complete text instruction and image inputs before spending the generate budget.
        contents = [{'role': 'user', 'parts': [{'text': INSTRUCTION}] + parts}]
        count = self._call(model, 'countTokens', {'contents': contents})
        tokens = count.get('totalTokens')
        if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0:
            raise EvidenceBlocked('Gemini did not supply a valid input-token count')
        response = self._call(model, 'generateContent', {
            'contents': contents,
            'generationConfig': {'temperature': 0, 'maxOutputTokens': 8192,
                                 'responseMimeType': 'application/json', 'responseSchema': SCHEMA},
        }, tokens)
        parsed=None
        try:
            candidate = response['candidates'][0]
            if candidate.get('finishReason') != 'STOP':
                raise EvidenceBlocked('Gemini response incomplete or blocked')
            body = ''.join(p.get('text', '') for p in candidate['content']['parts'] if not p.get('thought'))
            parsed = json.loads(body)
            validated = validate_extraction(source, parsed, model)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ContractError) as exc:
            if isinstance(parsed,dict):
                diagnostic=path.with_name(f'{key}.invalid-{time.time_ns()}.json')
                diagnostic.write_text(json.dumps(parsed,ensure_ascii=False,indent=2),encoding='utf-8')
            raise EvidenceBlocked('Invalid extracted facts; retry/escalation or review is required') from exc
        # Cache raw typed facts only after validation, retaining unresolved facts for review.
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
        return validated
