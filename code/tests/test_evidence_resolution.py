import sys
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buy_or_wait.evidence_resolution import resolve_candidates


class EvidenceResolutionTests(unittest.TestCase):
    def test_only_image_fills_blank_linked_event(self):
        event={'event_id':'e','amount':'','status':'pending'}
        data=SimpleNamespace(messages={},images={'image_x':{'user_id':'u','request_id':'r','related_event_id':'e'}},events={'e':event})
        report={'source_results':{'image_x':[{'source':{'source_id':'image_x'},'facts':[
            {'type':'amount_fill','scope':'event','amount':'12.5'}],'unresolved':[]}]}}
        self.assertEqual(Decimal('12.5'),resolve_candidates(report,data)['amount_overrides']['e'])

    def test_multiple_image_amount_fills_block_future_event(self):
        event={'event_id':'e','amount':'','status':'scheduled'}
        data=SimpleNamespace(messages={},images={'image_x':{'user_id':'u','request_id':'r','related_event_id':'e'}},events={'e':event})
        facts=[{'type':'amount_fill','scope':'event','amount':x} for x in ('10','20')]
        report={'source_results':{'image_x':[{'source':{'source_id':'image_x'},'facts':facts,'unresolved':[]}]}}
        result=resolve_candidates(report,data)
        self.assertNotIn('e',result['amount_overrides'])
        self.assertTrue(result['issues'][0]['blocking'])

    def test_message_amount_is_candidate_not_automatic_override(self):
        data=SimpleNamespace(messages={'message_x':{'user_id':'u','request_id':'r','related_event_id':'e'}},images={},
                             events={'e':{'event_id':'e','amount':'','status':'scheduled'}})
        report={'source_results':{'message_x':[{'source':{'source_id':'message_x'},'facts':[
            {'type':'amount_fill','scope':'event','amount':'12'}],'unresolved':[]}]}}
        result=resolve_candidates(report,data)
        self.assertFalse(result['amount_overrides'])
        self.assertEqual('12',result['facts_by_user']['u'][0]['amount'])

    def test_missing_image_blocks_only_unresolved_future_cash(self):
        rows={'image_old':{'user_id':'u','request_id':'r1','related_event_id':'old'},
              'image_due':{'user_id':'u','request_id':'r2','related_event_id':'due'}}
        events={'old':{'event_id':'old','amount':'','status':'settled'},
                'due':{'event_id':'due','amount':'','status':'scheduled'}}
        data=SimpleNamespace(messages={},images=rows,events=events)
        issues=resolve_candidates({'source_results':{}},data)['issues']
        self.assertEqual([False,True],[item['blocking'] for item in issues])

    def test_missing_visible_user_message_blocks_derived_request(self):
        message={'user_id':'u','request_id':'','related_event_id':'',
                 'sent_at':'2026-03-31T10:00:00Z'}
        data=SimpleNamespace(messages={'message_x':message},images={},events={},
            requests={'r':{'request_id':'r','user_id':'u','request_date':'2026-04-01'}})
        issue=resolve_candidates({'source_results':{}},data)['issues'][0]
        self.assertEqual(('r',True),(issue['request_id'],issue['blocking']))

    def test_missing_message_after_request_is_nonblocking(self):
        message={'user_id':'u','request_id':'r','related_event_id':'',
                 'sent_at':'2026-04-02T10:00:00Z'}
        data=SimpleNamespace(messages={'message_x':message},images={},events={},
            requests={'r':{'request_id':'r','user_id':'u','request_date':'2026-04-01'}})
        self.assertFalse(resolve_candidates({'source_results':{}},data)['issues'][0]['blocking'])


if __name__=='__main__':
    unittest.main()
