import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buy_or_wait.audit import audit
from buy_or_wait.contracts import ContractError, OUTPUT_COLUMNS, money, numeric_id, parse_plan, static_errors
from buy_or_wait.data import Dataset, read_csv, unique
from buy_or_wait.evaluator import evaluate


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = Dataset(Path(__file__).resolve().parents[2] / 'dataset')
        cls.samples = {s['request_id']: {c: s[c] for c in OUTPUT_COLUMNS}
                       for s in cls.data.tables['sample_requests']}

    def errors(self, rid, **updates):
        row = self.samples[rid] | updates
        req = self.data.requests[rid]
        return static_errors(row, req, self.data.profiles[req['user_id']],
                             self.data.options_by_request[rid], self.data.events)

    def test_integrity(self):
        report = audit(self.data)
        self.assertEqual([], report['errors'])
        self.assertEqual({}, report['observations']['sample_static_contract_errors'])

    def test_all_samples_are_statically_valid(self):
        for rid in self.samples:
            with self.subTest(rid=rid):
                self.assertEqual([], self.errors(rid))

    def test_request_objects_have_no_answers(self):
        for row in self.data.requests.values():
            self.assertFalse(set(OUTPUT_COLUMNS[1:]) & row.keys())

    def test_nonfinite_negative_blank_money(self):
        for value in ('NaN', 'Infinity', '-1', '', '-Infinity'):
            with self.subTest(value=value), self.assertRaises(ContractError):
                money(value)

    def test_numeric_option_order(self):
        self.assertLess(numeric_id('payment_option_2'), numeric_id('payment_option_10'))

    def test_bad_dates_and_plan_order(self):
        for plan in ('2026-02-30:1', '2026-01-02:1|2026-01-01:2', '20260101:1', '2026-01-01:0'):
            with self.subTest(plan=plan), self.assertRaises(ContractError):
                parse_plan(plan)

    def test_duplicate_request_rejected(self):
        with self.assertRaises(ContractError):
            unique([{'request_id': 'x'}, {'request_id': 'x'}], 'request_id')

    def test_blank_amount_does_not_become_zero(self):
        missing = [e for e in self.data.events.values() if e['amount'] == '']
        self.assertEqual(16, len(missing))
        for event in missing:
            with self.assertRaises(ContractError):
                money(event['amount'])

    def test_amount_bounds(self):
        self.assertIn('AMOUNT_BOUNDS', self.errors('request_01', amount_safe_to_pay='99999999'))

    def test_wrong_partial_amount_and_count(self):
        for plan in ('2024-09-04:28820|2024-09-15:1', '2024-09-04:39660'):
            self.assertIn('PARTIAL_SCHEDULE', self.errors('request_19', payment_plan=plan))

    def test_shifted_installment_rejected(self):
        row = self.samples['request_02']
        plan = row['payment_plan'].replace('2025-08-08', '2025-08-09')
        self.assertIn('INSTALLMENT_SCHEDULE', self.errors('request_02', payment_plan=plan))

    def test_wait_cannot_move_payment(self):
        self.assertIn('SINGLE_PAYMENT_SCHEDULE', self.errors('request_03', payment_plan='2019-11-14:5491000'))

    def test_wait_after_deadline(self):
        found = self.errors('request_03', payment_plan='2019-11-16:5491000', earliest_date_for_full_payment='2019-11-16')
        self.assertIn('PAYMENT_OUTSIDE_WINDOW', found)

    def test_unknown_user_change(self):
        self.assertIn('CHANGE_TARGET', self.errors('request_06', spending_changes_needed='stop:event_1815'))

    def test_protected_and_fixed_change(self):
        found = self.errors('request_06', spending_changes_needed='stop:event_472')
        self.assertIn('CHANGE_PROTECTED', found)
        self.assertIn('STOP_NOT_ALLOWED', found)

    def test_reduction_floor(self):
        self.assertIn('REDUCTION_BELOW_MINIMUM', self.errors('request_21', spending_changes_needed='reduce_to:event_1816:1'))

    def test_duplicate_change(self):
        found = self.errors('request_21', spending_changes_needed='stop:event_1816|reduce_to:event_1816:23.5')
        self.assertIn('DUPLICATE_CHANGE_TARGET', found)

    def test_stoppable_is_not_implicitly_reducible(self):
        found = self.errors('request_06', spending_changes_needed='reduce_to:event_476:1')
        self.assertIn('REDUCE_NOT_ALLOWED', found)

    def test_evaluator_self_check_and_numeric_normalization(self):
        predictions = copy.deepcopy(list(self.samples.values()))
        predictions[0]['amount_safe_to_pay'] += '.00'
        report = evaluate(predictions, self.data)
        self.assertEqual({}, report['field_mismatches'])
        self.assertEqual({}, report['static_contract_errors'])
        for metric in report['metrics'].values():
            self.assertEqual(25, metric['matches'])

    def test_evaluator_catches_corruption_and_missing_rows(self):
        predictions = copy.deepcopy(list(self.samples.values()))
        predictions[0]['amount_safe_to_pay'] = '0'
        predictions.pop()
        report = evaluate(predictions, self.data)
        self.assertIn('request_01', report['field_mismatches'])
        self.assertIn('request_01', report['static_contract_errors'])
        self.assertEqual(['request_25'], report['missing_ids'])


if __name__ == '__main__':
    unittest.main()
