import copy
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buy_or_wait.contracts import ContractError
from buy_or_wait.evidence import Source, cache_key, validate_extraction, amount_in_quote


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source = Source('message_x', 'message', 'user_x', 'request_x', '',
                             '2026-01-01T09:30:00Z', 'Monthly salary is EUR 1000 effective February 1.', {})
        self.fact = {'type': 'salary_change', 'scope': 'user', 'amount': '1000', 'currency': 'EUR',
                     'effective_date': '2026-02-01', 'settlement_date': '', 'recurrence': 'recurring',
                     'source_identity': '', 'quote': 'Monthly salary is EUR 1000 effective February 1.', 'uncertainty': ''}

    def result(self, fact=None):
        return validate_extraction(self.source, {'facts': [fact or self.fact], 'unresolved': []}, 'gemini-3.5-flash-lite')

    def test_request_link_does_not_make_salary_request_scoped(self):
        self.assertEqual('user', self.result()['facts'][0]['scope'])

    def test_effective_date_not_assumed_settlement(self):
        self.assertEqual('', self.result()['facts'][0]['settlement_date'])

    def test_model_cannot_supply_ids(self):
        with self.assertRaises(ContractError):
            self.result(self.fact | {'target_event_id': 'event_other'})

    def test_model_source_identity_is_ignored_and_normalized(self):
        result=self.result(self.fact | {'source_identity':'message_other'})
        self.assertEqual('message_x',result['facts'][0]['source_identity'])
        self.assertIn('Model-supplied source identity was ignored and normalized',result['unresolved'])

    def test_blank_source_identity_is_normalized(self):
        self.assertEqual('message_x', self.result()['facts'][0]['source_identity'])

    def test_invented_quote_is_rejected(self):
        with self.assertRaises(ContractError):
            self.result(self.fact | {'quote': 'Salary is 9999'})

    def test_context_amount_without_quote_support_is_unresolved(self):
        result = self.result(self.fact | {'amount': '9999'})
        self.assertEqual('unresolved', result['status'])
        self.assertIn('Extracted amount is not numerically supported by its source quote', result['unresolved'])

    def test_numeric_quote_grouping(self):
        for quote in ('EUR 1000', 'EUR 1,000.00', 'INR 1,00,000.00'):
            self.assertTrue(amount_in_quote('100000' if '1,00,000' in quote else '1000', quote))
        self.assertFalse(amount_in_quote('1000', 'EUR 10000'))
        self.assertFalse(amount_in_quote('1.5', 'EUR 1,50'))

    def test_sentence_punctuation_is_not_a_decimal_separator(self):
        self.assertTrue(amount_in_quote('42750000', 'IDR 42750000. Changes follow.'))
        self.assertTrue(amount_in_quote('1037.52', 'Pay is EUR 1037.52.'))
        self.assertFalse(amount_in_quote('1037', 'Pay is EUR 1037.52.'))

    def test_missing_link_remains_unresolved(self):
        self.assertEqual('unresolved', self.result(self.fact | {'scope': 'event'})['status'])

    def test_missing_required_amount_remains_unresolved(self):
        self.assertEqual('unresolved', self.result(self.fact | {'amount': ''})['status'])

    def test_uncertainty_is_preserved(self):
        self.assertEqual('unresolved', self.result(self.fact | {'uncertainty': 'Conflicting amounts'})['status'])

    def test_nan_rejected(self):
        with self.assertRaises(ContractError):
            self.result(self.fact | {'amount': 'NaN'})

    def test_cache_changes_with_context_and_model(self):
        original = cache_key(self.source, 'gemini-3.5-flash-lite')
        self.assertNotEqual(original, cache_key(replace(self.source, context={'event': 'new'}), 'gemini-3.5-flash-lite'))
        self.assertNotEqual(original, cache_key(self.source, 'gemini-3.6-flash'))

    def test_unapproved_preview_rejected(self):
        with self.assertRaises(ContractError):
            cache_key(self.source, 'gemini-3-pro-preview')

    def test_no_fake_image_observation_timestamp(self):
        image = Source('image_x', 'image', 'user_x', 'request_x', 'event_x', '', '', {}, 'image_hash')
        self.assertEqual('', image.observed_at)

    def test_empty_extraction_not_silent_success(self):
        with self.assertRaises(ContractError):
            validate_extraction(self.source, {'facts': [], 'unresolved': []}, 'gemini-3.5-flash-lite')


if __name__ == '__main__':
    unittest.main()
