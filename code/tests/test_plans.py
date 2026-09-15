import sys
import unittest
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buy_or_wait.cashflow import CashState, Flow
from buy_or_wait.contracts import ContractError
from buy_or_wait.plans import Candidate, no_change_candidates, rank

DAY = date(2026,1,1)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.request = dict(request_id='request_1', request_date='2026-01-01', requested_amount='100',
                            desired_completion_date='2026-01-05', allows_partial_payment='true')
        self.profile = dict(payment_methods_user_will_consider='full_payment|partial_payment|installments',
                            max_installment_months='2')
        self.state = CashState(DAY, DAY+timedelta(days=4), D('100'), D('20'),
                               (Flow('salary', DAY+timedelta(days=2), D('100'), 'confirmed'),), 'debits_first')
        self.offer = dict(payment_option_id='option_1', request_id='request_1', payment_method='installments',
                          payment_amount='50', number_of_payments='2', first_payment_date='2026-01-01',
                          payment_frequency_days='2', financing_fee='0', total_payable_amount='100')

    def generate(self, **kwargs):
        return no_change_candidates(kwargs.pop('state', self.state), self.request, self.profile,
                                    kwargs.pop('options', []), installment_eligible=kwargs.pop('eligible', lambda o,p: True))

    def test_partial_exact_and_earlier_start_than_wait(self):
        result = self.generate()
        c = result['candidates'][0]
        self.assertEqual('partial_payment', c.method)
        self.assertEqual(((DAY,D('80')), (DAY+timedelta(days=2),D('20'))), c.payments)

    def test_installment_exact_supplied_schedule(self):
        result = self.generate(options=[self.offer])
        c = next(c for c in result['candidates'] if c.method == 'installments')
        self.assertEqual(((DAY,D('50')), (DAY+timedelta(days=2),D('50'))), c.payments)

    def test_payment_preferences_do_not_change_capacity(self):
        expected = self.generate()['capacity']
        self.profile['payment_methods_user_will_consider'] = ''
        result = self.generate(options=[self.offer])
        self.assertFalse(result['candidates'])
        self.assertEqual(expected, result['capacity'])

    def test_duration_policy_required_and_enforced(self):
        self.assertFalse(any(c.method == 'installments' for c in self.generate(options=[self.offer], eligible=lambda o,p: False)['candidates']))

    def test_deadline_rejects_partial_and_wait(self):
        self.request['desired_completion_date'] = '2026-01-02'
        self.assertFalse(self.generate()['candidates'])

    def test_baseline_breach_never_becomes_wait(self):
        s = replace(self.state, flows=self.state.flows+(Flow('bill', DAY+timedelta(days=1), D('-90'), 'essential'),))
        self.assertFalse(self.generate(state=s)['candidates'])

    def test_bad_fee_total_is_error_not_unaffordable(self):
        with self.assertRaises(ContractError):
            self.generate(options=[self.offer | {'financing_fee': '1'}])

    def test_ranking_each_criterion(self):
        deadline = DAY+timedelta(days=4)
        base = Candidate('installments', ((DAY,D('50')), (DAY+timedelta(days=2),D('50'))), 'option_2')
        alternatives = [
            replace(base, payments=((DAY,D('50')), (DAY+timedelta(days=5),D('50')))),
            replace(base, changes=('stop:event_1',)),
            replace(base, payments=((DAY,D('51')), (DAY+timedelta(days=2),D('50')))),
            replace(base, payments=((DAY+timedelta(days=1),D('50')), (DAY+timedelta(days=2),D('50')))),
            replace(base, payments=((DAY,D('25')), (DAY+timedelta(days=1),D('25')), (DAY+timedelta(days=2),D('50')))),
            replace(base, option_id='option_10'),
        ]
        for other in alternatives:
            self.assertLess(rank(base, deadline), rank(other, deadline))


if __name__ == '__main__':
    unittest.main()
