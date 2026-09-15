import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buy_or_wait.cash_state import explicit_flows
from buy_or_wait.contracts import ContractError


def event(eid='a', **values):
    return dict(event_id=eid, user_id='u', status='scheduled', direction='debit',
                amount='10', currency='EUR', settlement_date='2026-01-02',
                linked_event_id='') | values


def classify(events, **kwargs):
    return explicit_flows(events, user_id='u', home_currency='EUR', start=date(2026,1,1),
                          end=date(2026,1,5), rates=kwargs.pop('rates', {}), **kwargs)


class CashStateTests(unittest.TestCase):
    def test_reserve_pending_debit_once(self):
        flows, _ = classify([event(status='pending')])
        self.assertEqual(1, len(flows))
        self.assertEqual(date(2026,1,1), flows[0].day)
        self.assertEqual(Decimal('-10'), flows[0].amount)

    def test_pending_credit_not_confirmable(self):
        self.assertFalse(classify([event(status='pending', direction='credit')], confirmed_credits={'a'})[0])

    def test_scheduled_credit_needs_confirmation(self):
        e = event(direction='credit')
        self.assertFalse(classify([e])[0])
        self.assertEqual(Decimal('10'), classify([e], confirmed_credits={'a'})[0][0].amount)

    def test_history_never_replayed(self):
        self.assertFalse(classify([event(status='settled', settlement_date='2025-12-31')])[0])

    def test_link_does_not_erase_distinct_cash(self):
        flows, _ = classify([event(), event('b', direction='credit', linked_event_id='a')], confirmed_credits={'b'})
        self.assertEqual(2, len(flows))

    def test_only_explicit_supersession_deduplicates(self):
        flows, _ = classify([event(status='pending'), event('b', linked_event_id='a')], superseded={'a'})
        self.assertEqual(['b'], [f.identity for f in flows])

    def test_excluded_cash_states(self):
        for status in ('failed', 'cancelled', 'unrealized'):
            self.assertFalse(classify([event(status=status, amount='')])[0])
        self.assertFalse(classify([event(direction='non_cash', amount='')])[0])

    def test_missing_required_amount_blocks(self):
        with self.assertRaises(ContractError):
            classify([event(amount='')])

    def test_fx_pending_uses_settlement_date_and_direction(self):
        rates = {('2026-01-02', 'USD', 'EUR'): '0.9'}
        f = classify([event(status='pending', currency='USD')], rates=rates)[0][0]
        self.assertEqual(Decimal('-9'), f.amount)
        with self.assertRaises(ContractError):
            classify([event(currency='USD')], rates={('2026-01-01', 'EUR', 'USD'): '1.1'})

    def test_ambiguous_time_states_fail(self):
        for e in (event(status='settled'), event(settlement_date='2025-12-30')):
            with self.assertRaises(ContractError):
                classify([e])

    def test_ownership_and_resolution_ids(self):
        with self.assertRaises(ContractError):
            classify([event(user_id='other')])
        with self.assertRaises(ContractError):
            classify([event()], confirmed_credits={'unknown'})


if __name__ == '__main__':
    unittest.main()
