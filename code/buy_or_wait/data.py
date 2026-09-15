"""Read-only CSV ingestion. Sample answer fields never enter request objects."""
from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from .contracts import ContractError, OUTPUT_COLUMNS, REQUEST_COLUMNS

SCHEMAS = {
    'requests': REQUEST_COLUMNS,
    'sample_requests': REQUEST_COLUMNS + OUTPUT_COLUMNS[1:],
    'output': OUTPUT_COLUMNS,
    'financial_profiles': ('user_id', 'home_currency', 'current_available_balance', 'minimum_balance_to_keep',
        'financial_priorities', 'expense_categories_to_protect', 'expense_categories_user_is_willing_to_reduce',
        'expense_categories_user_is_willing_to_stop', 'payment_methods_user_will_consider', 'max_installment_months'),
    'financial_events': ('event_id', 'user_id', 'event_type', 'description', 'category', 'direction', 'amount',
        'currency', 'event_date', 'settlement_date', 'status', 'linked_event_id', 'flexibility', 'minimum_allowed_amount'),
    'exchange_rates': ('rate_date', 'from_currency', 'to_currency', 'rate'),
    'request_payment_options': ('payment_option_id', 'request_id', 'payment_method', 'payment_amount',
        'number_of_payments', 'first_payment_date', 'payment_frequency_days', 'financing_fee', 'total_payable_amount'),
    'messages': ('message_id', 'user_id', 'request_id', 'related_event_id', 'sent_at', 'source_type', 'message_text'),
    'images': ('image_id', 'user_id', 'request_id', 'related_event_id'),
}


def read_csv(path: Path, columns: tuple[str, ...] | None = None) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if columns is not None and tuple(reader.fieldnames or ()) != columns:
            raise ContractError(f'{path.name}: unexpected columns: {reader.fieldnames}')
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ContractError(f'{path.name}: malformed CSV row')
    return rows


def unique(rows: list[dict], field: str) -> dict[str, dict]:
    result = {}
    for row in rows:
        key = row[field]
        if not key or key in result:
            raise ContractError(f'Empty/duplicate {field}: {key!r}')
        result[key] = row
    return result


class Dataset:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.tables = {name: read_csv(self.root / f'{name}.csv', schema)
                       for name, schema in SCHEMAS.items()}
        self.profiles = unique(self.tables['financial_profiles'], 'user_id')
        self.events = unique(self.tables['financial_events'], 'event_id')
        self.options = unique(self.tables['request_payment_options'], 'payment_option_id')
        self.messages = unique(self.tables['messages'], 'message_id')
        self.images = unique(self.tables['images'], 'image_id')
        evaluation = unique(self.tables['requests'], 'request_id')
        samples = unique(self.tables['sample_requests'], 'request_id')
        if evaluation.keys() & samples.keys():
            raise ContractError('Sample/evaluation request IDs overlap')
        self.requests = {key: {column: row[column] for column in REQUEST_COLUMNS}
                         for key, row in (evaluation | samples).items()}
        self.events_by_user = defaultdict(list)
        self.options_by_request = defaultdict(list)
        for event in self.events.values():
            self.events_by_user[event['user_id']].append(event)
        for option in self.options.values():
            self.options_by_request[option['request_id']].append(option)

    def fingerprint(self, *, include_output: bool = False) -> dict[str, str]:
        # Predictions are derived output and must never invalidate evidence caches
        # or masquerade as an evidence input. Audit callers may opt in explicitly.
        files = [self.root / f'{name}.csv' for name in SCHEMAS if include_output or name != 'output']
        files += [self.root / 'media' / 'images' / f'{i}.png' for i in self.images]
        return {str(path.relative_to(self.root)).replace('\\', '/'):
                hashlib.sha256(path.read_bytes()).hexdigest() for path in files if path.is_file()}
