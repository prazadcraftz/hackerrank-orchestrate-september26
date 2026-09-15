import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buy_or_wait.cashflow import CashState, Flow, capacity, replay
from buy_or_wait.contracts import ContractError

START = date(2026, 1, 1)


def state(flows=(), opening='100', minimum='20', days=5, intraday='debits_first'):
    return CashState(START, START + timedelta(days=days-1), D(opening), D(minimum),
                     tuple(Flow(str(i), START + timedelta(days=n), D(amount), 'test')
                           for i, (n, amount) in enumerate(flows)), intraday)


class CashflowTests(unittest.TestCase):
    def test_empty_forecast(self):
        result = capacity(state(), D('90'))
        self.assertEqual(D('80'), result['safe_today'])
        self.assertIsNone(result['earliest_full'])

    def test_salary_enables_wait(self):
        s = state([(1, '50')])
        self.assertEqual(START + timedelta(days=1), capacity(s, D('100'))['earliest_full'])
        self.assertTrue(replay(s, [(START + timedelta(days=1), D('100'))])['safe'])

    def test_later_expense_limits_now(self):
        self.assertEqual(D('30'), capacity(state([(4, '-50')]), D('100'))['safe_today'])

    def test_later_salary_cannot_hide_earlier_breach(self):
        s = state([(1, '-90'), (2, '200')])
        self.assertFalse(capacity(s, D('20'))['baseline_safe'])
        self.assertIsNone(capacity(s, D('20'))['earliest_full'])
        self.assertFalse(replay(s, [(START + timedelta(days=3), D('20'))])['safe'])

    def test_intraday_not_netted(self):
        s = state([(1, '-90'), (1, '90')])
        self.assertFalse(replay(s, [])['safe'])
        self.assertTrue(replay(state([(1, '-90'), (1, '90')], intraday='credits_first'), [])['safe'])

    def test_payment_after_salary(self):
        s = state([(0, '100')])
        self.assertEqual(D('180'), capacity(s, D('200'))['safe_today'])

    def test_starting_breach_not_hidden(self):
        s = state([(0, '100')], opening='10')
        self.assertFalse(replay(s, [])['safe'])
        self.assertEqual(D('0'), capacity(s, D('10'))['safe_today'])

    def test_exact_horizon_boundary(self):
        s = state([(4, '-30')])
        self.assertEqual(D('50'), capacity(s, D('100'))['safe_today'])
        with self.assertRaises(ContractError):
            replay(s, [(START + timedelta(days=5), D('1'))])

    def test_outside_flows_rejected(self):
        with self.assertRaises(ContractError):
            state([(5, '-1')])

    def test_duplicate_identity_rejected(self):
        f = Flow('x', START, D('-1'), 'reserve')
        with self.assertRaises(ContractError):
            CashState(START, START, D('100'), D('20'), (f, f), 'debits_first')

    def test_round_capacity_down(self):
        s = state(opening='100.009')
        self.assertEqual(D('80.00'), capacity(s, D('100'))['safe_today'])
        self.assertFalse(replay(s, [(START, D('80.01'))])['safe'])

    def test_partial_payments_accumulate(self):
        s = state([(2, '40')])
        self.assertTrue(replay(s, [(START, D('80')), (START + timedelta(days=2), D('40'))])['safe'])
        self.assertFalse(replay(s, [(START, D('80')), (START + timedelta(days=2), D('40.01'))])['safe'])

    def test_invalid_payment_values(self):
        for value in ('NaN', '-1', '0', 'Infinity'):
            with self.assertRaises(ContractError):
                replay(state(), [(START, D(value))])

    def test_deterministic_random_capacity_replay_and_monotonicity(self):
        rng = Random(41)
        for _ in range(100):
            flows = [(rng.randrange(5), str(rng.randrange(-30, 60))) for _ in range(8)]
            s = state(flows)
            result = capacity(s, D('1000'))
            self.assertLessEqual(result['safe_today'], capacity(state(flows, opening='110'), D('1000'))['safe_today'])
            self.assertGreaterEqual(result['safe_today'], capacity(state(flows, minimum='30'), D('1000'))['safe_today'])
            for day, amount in result['capacity_by_date'].items():
                if result['baseline_safe']:
                    self.assertTrue(replay(s, [(day, amount)] if amount else [])['safe'])
                    self.assertFalse(replay(s, [(day, amount + D('.01'))])['safe'])


if __name__ == '__main__':
    unittest.main()
