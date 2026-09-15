"""Input integrity and semantic observations, without producing predictions."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal

from .contracts import CURRENCIES, FLEXIBILITY, iso_date, money, numeric_id, option_schedule, positive_int, static_errors, OUTPUT_COLUMNS
from .data import Dataset, unique


def audit(data: Dataset) -> dict:
    errors, observations = [], {}
    missing_amounts, future_events, same_day, after_request_messages = [], [], [], []
    rates = {}
    for rate in data.tables['exchange_rates']:
        key = (rate['rate_date'], rate['from_currency'], rate['to_currency'])
        iso_date(key[0])
        if key in rates:
            errors.append(f'Duplicate rate: {key}')
        rates[key] = money(rate['rate'], allow_zero=False)
        if key[1] not in CURRENCIES or key[2] not in CURRENCIES:
            errors.append(f'Invalid rate currency: {key}')
    for p in data.profiles.values():
        money(p['current_available_balance'])
        money(p['minimum_balance_to_keep'])
        if p['home_currency'] not in CURRENCIES:
            errors.append(f'Unknown home currency: {p["user_id"]}')
        if p['max_installment_months']:
            positive_int(p['max_installment_months'])
    by_user = {}
    for r in data.requests.values():
        if r['user_id'] not in data.profiles:
            errors.append(f'Missing profile: {r["request_id"]}')
        by_user.setdefault(r['user_id'], []).append(r)
        if iso_date(r['desired_completion_date']) < iso_date(r['request_date']):
            errors.append(f'Deadline before request: {r["request_id"]}')
        money(r['requested_amount'], allow_zero=False)
        if r['allows_partial_payment'] not in {'true', 'false'}:
            errors.append(f'Invalid partial flag: {r["request_id"]}')
        if not 2 <= len(data.options_by_request[r['request_id']]) <= 4:
            errors.append(f'Option count: {r["request_id"]}')
    image_events = Counter(i['related_event_id'] for i in data.images.values())
    for event in data.events.values():
        eid = event['event_id']
        if event['user_id'] not in data.profiles:
            errors.append(f'Unknown event user: {eid}')
            continue
        iso_date(event['event_date'])
        if event['settlement_date']:
            iso_date(event['settlement_date'])
        if event['status'] not in {'pending', 'scheduled', 'settled', 'cancelled', 'failed', 'unrealized'}:
            errors.append(f'Unknown status: {eid}')
        if event['flexibility'] not in FLEXIBILITY:
            errors.append(f'Unknown flexibility: {eid}')
        if event['direction'] not in {'credit', 'debit', 'non_cash'}:
            errors.append(f'Unknown direction: {eid}')
        if event['amount']:
            money(event['amount'])
        else:
            missing_amounts.append(eid)
            if not image_events[eid]:
                errors.append(f'Blank amount without image: {eid}')
        if event['minimum_allowed_amount']:
            money(event['minimum_allowed_amount'])
        parent_id = event['linked_event_id']
        if parent_id:
            parent = data.events.get(parent_id)
            if not parent or parent['user_id'] != event['user_id']:
                errors.append(f'Invalid lifecycle link: {eid}')
            visited, current = {eid}, parent_id
            while current in data.events:
                if current in visited:
                    errors.append(f'Lifecycle cycle: {eid}')
                    break
                visited.add(current)
                current = data.events[current]['linked_event_id']
        home = data.profiles[event['user_id']]['home_currency']
        if event['currency'] not in CURRENCIES:
            errors.append(f'Unknown event currency: {eid}')
        if (event['currency'] != home and event['direction'] != 'non_cash'
                and event['status'] in {'settled', 'pending', 'scheduled'}):
            key = (event['settlement_date'], event['currency'], home)
            if key not in rates:
                errors.append(f'Missing exact FX: {eid}:{key}')
        for req in by_user.get(event['user_id'], []):
            if event['event_date'] > req['request_date']:
                future_events.append({'event_id': eid, 'request_id': req['request_id'], 'status': event['status']})
            if event['settlement_date'] == req['request_date']:
                same_day.append({'event_id': eid, 'request_id': req['request_id'], 'status': event['status']})
    for kind, sources in [('message', data.messages), ('image', data.images)]:
        for sid, source in sources.items():
            if source['user_id'] not in data.profiles:
                errors.append(f'Unknown source user: {sid}')
            for field, index in [('request_id', data.requests), ('related_event_id', data.events)]:
                linked = source[field]
                if linked and (linked not in index or index[linked]['user_id'] != source['user_id']):
                    errors.append(f'Cross-user or missing source target: {sid}:{field}')
            if kind == 'image':
                if not (data.root / 'media' / 'images' / f'{sid}.png').is_file():
                    errors.append(f'Missing image: {sid}')
            else:
                stamp = datetime.fromisoformat(source['sent_at'].replace('Z', '+00:00'))
                if stamp.tzinfo is None:
                    errors.append(f'Message timestamp lacks timezone: {sid}')
                for req in by_user.get(source['user_id'], []):
                    if stamp.date() > iso_date(req['request_date']):
                        after_request_messages.append({'message_id': sid, 'request_id': req['request_id']})
    rounding = []
    for oid, option in data.options.items():
        numeric_id(oid)
        if option['request_id'] not in data.requests:
            errors.append(f'Option request missing: {oid}')
            continue
        schedule = option_schedule(option)
        total = sum((a for _, a in schedule), Decimal(0))
        supplied_total = money(option['total_payable_amount'])
        requested = money(data.requests[option['request_id']]['requested_amount'])
        fee = money(option['financing_fee'])
        if total != supplied_total or requested + fee != supplied_total:
            rounding.append({'payment_option_id': oid, 'schedule_total': str(total),
                             'supplied_total': str(supplied_total), 'requested_plus_fee': str(requested + fee)})
        if option['payment_method'] not in {'full_payment', 'installments'}:
            errors.append(f'Unknown option method: {oid}')
    template = unique(data.tables['output'], 'request_id')
    expected = {r['request_id'] for r in data.tables['requests']}
    if template.keys() != expected:
        errors.append('Output template ID coverage')
    sample_errors = {}
    for sample in data.tables['sample_requests']:
        req = data.requests[sample['request_id']]
        row = {c: sample[c] for c in OUTPUT_COLUMNS}
        found = static_errors(row, req, data.profiles[req['user_id']], data.options_by_request[req['request_id']], data.events)
        if found:
            sample_errors[req['request_id']] = found
    observations.update(
        blank_amount_event_ids=missing_amounts,
        future_event_dates=future_events,
        request_day_settlements=same_day,
        after_request_messages=after_request_messages,
        option_total_discrepancies=rounding,
        sample_static_contract_errors=sample_errors,
        event_status_counts=dict(Counter(e['status'] for e in data.events.values())),
        flexibility_counts=dict(Counter(e['flexibility'] for e in data.events.values())),
        linked_events=sum(bool(e['linked_event_id']) for e in data.events.values()),
    )
    return {'counts': {name: len(rows) for name, rows in data.tables.items()},
            'errors': errors, 'observations': observations,
            'input_sha256': data.fingerprint(),
            'limitations': ['Static validation is not cash-flow safety validation.',
                           'Option duration, recurrence legality, and explanations require semantic validation.',
                           'Sample answers are inspected only by the audit/evaluator, never prediction request objects.']}
