import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buy_or_wait.contracts import ContractError
from buy_or_wait.evidence_resolution import resolve_candidates
from buy_or_wait.reviewed_images import load_reviewed_images, merge_reviewed_images


def fact(amount='12.50'):
    return {'type':'amount_fill','scope':'event','amount':amount,'currency':'EUR',
            'effective_date':'','settlement_date':'','recurrence':'one_time',
            'source_identity':'image_x','quote':f'Total EUR {amount}','uncertainty':''}


class ReviewedImageTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        root=Path(self.folder.name)
        media=root/'media'/'images';media.mkdir(parents=True)
        content=b'exact reviewed image bytes'
        (media/'image_x.png').write_bytes(content)
        self.digest=hashlib.sha256(content).hexdigest()
        event={'event_id':'e','user_id':'u','amount':'','status':'scheduled'}
        request={'request_id':'r','user_id':'u'}
        self.data=SimpleNamespace(root=root,
            messages={},
            images={'image_x':{'image_id':'image_x','user_id':'u','request_id':'r','related_event_id':'e'}},
            events={'e':event},requests={'r':request},profiles={'u':{'home_currency':'EUR'}})

    def tearDown(self):
        self.folder.cleanup()

    def manifest(self, **entry_changes):
        entry={'source_id':'image_x','image_sha256':self.digest,
               'facts':[fact()],'unresolved':[]}|entry_changes
        path=Path(self.folder.name)/'review.json'
        path.write_text(json.dumps({'schema_version':'1','review_method':'approved visual review',
                                    'reviews':[entry]}),encoding='utf-8')
        return path

    def test_hash_bound_review_resolves_blank_event(self):
        reviewed=load_reviewed_images(self.manifest(),self.data)
        base={'status':'needs_review','source_results':{'image_x':[]},
              'blocked_sources':{'image_x':'missing'}}
        merged=merge_reviewed_images(base,reviewed)
        self.assertEqual('candidate_facts_ready',merged['status'])
        self.assertEqual('manual-local-review',merged['source_results']['image_x'][0]['model'])
        self.assertEqual('12.50',str(resolve_candidates(merged,self.data)['amount_overrides']['e']))
        self.assertEqual('needs_review',base['status'])  # merge never mutates its input

    def test_changed_image_bytes_reject_stale_review(self):
        path=self.manifest(image_sha256='0'*64)
        with self.assertRaisesRegex(ContractError,'hash differs'):
            load_reviewed_images(path,self.data)

    def test_manual_review_cannot_override_valid_model_candidate(self):
        reviewed=load_reviewed_images(self.manifest(),self.data)
        base={'status':'candidate_facts_ready','source_results':{'image_x':[{'status':'candidate_facts'}]},
              'blocked_sources':{}}
        with self.assertRaisesRegex(ContractError,'cannot override'):
            merge_reviewed_images(base,reviewed)

    def test_ambiguous_manual_amounts_remain_unresolved(self):
        entry={'facts':[fact('12.50'),fact('13.00')],
               'unresolved':['Two visible totals have different meanings.']}
        reviewed=load_reviewed_images(self.manifest(**entry),self.data)
        base={'status':'needs_review','source_results':{'image_x':[]},
              'blocked_sources':{'image_x':'missing'}}
        merged=merge_reviewed_images(base,reviewed)
        resolved=resolve_candidates(merged,self.data)
        self.assertNotIn('e',resolved['amount_overrides'])
        self.assertEqual('needs_review',merged['status'])
        self.assertTrue(resolved['issues'][0]['blocking'])


if __name__=='__main__':
    unittest.main()
