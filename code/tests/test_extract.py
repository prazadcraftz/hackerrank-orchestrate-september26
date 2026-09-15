import sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buy_or_wait.evidence import Source
from buy_or_wait.extract import extract_all
from buy_or_wait.gemini import EvidenceBlocked,QuotaBlocked


class FakeClient:
    def __init__(self,*args,**kwargs):
        self.usage=[];self.cache_hits=0;self.models=[]
    def extract(self,source,model,image):
        self.models.append(model)
        if model.endswith('flash-lite'):
            raise QuotaBlocked('lite limited')
        return {'status':'candidate_facts','facts':[{'type':'informational'}],'unresolved':[]}
    def close(self): pass


class ExtractTests(unittest.TestCase):
    def test_lite_quota_uses_approved_flash_fallback(self):
        data=SimpleNamespace(fingerprint=lambda:{'x':'y'})
        source=Source('message_x','message','u','','','','Text',{})
        with tempfile.TemporaryDirectory() as folder,patch('buy_or_wait.extract.GeminiExtractor',FakeClient),patch('buy_or_wait.extract.sources',return_value=[(source,None)]):
            result=extract_all(data,Path(folder)/'cache',Path(folder)/'report.json')
            self.assertEqual('candidate_facts_ready',result['status'])
            self.assertEqual('candidate_facts',result['source_results']['message_x'][-1]['status'])

    def test_resume_merges_prior_usage_and_source_results(self):
        data=SimpleNamespace(fingerprint=lambda:{'x':'y'})
        source=Source('message_x','message','u','','','','Text',{})
        with tempfile.TemporaryDirectory() as folder:
            destination=Path(folder)/'report.json'
            destination.write_text('{"sample_only":false,"input_sha256":{"x":"y"},"source_results":{"old":[]},"blocked_sources":{},"usage_previous_runs":[{"model":"a"}],"usage_this_run":[{"model":"b"}],"cache_hits_previous_runs":2,"cache_hits_this_run":3}',encoding='utf-8')
            with patch('buy_or_wait.extract.GeminiExtractor',FakeClient),patch('buy_or_wait.extract.sources',return_value=[(source,None)]):
                result=extract_all(data,Path(folder)/'cache',destination)
            self.assertIn('old',result['source_results'])
            self.assertEqual(2,len(result['usage_previous_runs']))
            self.assertEqual(5,result['cache_hits_previous_runs'])

    def test_exhausted_fallback_does_not_stop_other_primary_sources(self):
        class SelectiveClient(FakeClient):
            def extract(self,source,model,image):
                self.models.append((source.source_id,model))
                if source.source_id=='message_bad' and model.endswith('flash-lite'):
                    raise EvidenceBlocked('invalid primary')
                if model=='gemini-3.6-flash':
                    raise QuotaBlocked('flash limited')
                return {'status':'candidate_facts','facts':[{'type':'informational'}],'unresolved':[]}
        data=SimpleNamespace(fingerprint=lambda:{'x':'y'})
        items=[(Source('message_bad','message','u','','','','Bad',{}),None),
               (Source('message_good','message','u','','','','Good',{}),None)]
        with tempfile.TemporaryDirectory() as folder,patch('buy_or_wait.extract.GeminiExtractor',SelectiveClient),patch('buy_or_wait.extract.sources',return_value=items):
            result=extract_all(data,Path(folder)/'cache',Path(folder)/'report.json')
        self.assertEqual('quota_blocked',result['status'])
        self.assertEqual('candidate_facts',result['source_results']['message_good'][-1]['status'])
        self.assertIn('message_bad',result['blocked_sources'])

if __name__=='__main__':unittest.main()
