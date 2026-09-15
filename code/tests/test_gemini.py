import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buy_or_wait.evidence import Source, cache_key
from buy_or_wait.gemini import GeminiExtractor, QuotaBlocked, ModelUnavailable


class GeminiTests(unittest.TestCase):
    def test_invalid_cache_is_not_trusted_or_counted(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Source('message_x','message','user_x','','','','Text',{})
            model='gemini-3.5-flash-lite'
            invalid={'facts':[{'type':'informational','scope':'informational','amount':'','currency':'',
                'effective_date':'','settlement_date':'','recurrence':'unknown','source_identity':'message_x',
                'quote':'Invented quote','uncertainty':''}],'unresolved':[]}
            Path(folder,f'{cache_key(source,model)}.json').write_text(json.dumps(invalid),encoding='utf-8')
            def transport(model,operation,body):
                if operation=='countTokens':
                    return {'totalTokens':10}
                valid={'facts':[invalid['facts'][0]|{'quote':'Text'}],'unresolved':[]}
                return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(valid)}]}}]}
            client=GeminiExtractor(Path(folder),transport=transport)
            try:
                result=client.extract(source,model)
                self.assertEqual('candidate_facts',result['status'])
                self.assertEqual(0,client.cache_hits)
                self.assertEqual(1,len(list(Path(folder).glob('*.invalid-*.json'))))
            finally: client.close()

    def test_unavailable_model_is_a_run_blocker(self):
        with tempfile.TemporaryDirectory() as folder:
            client = GeminiExtractor(Path(folder), transport=lambda *args: {})
            client.key = 'test-only'
            try:
                with patch('buy_or_wait.gemini.urlopen', side_effect=HTTPError('https://example.invalid', 404, 'Not Found', {}, None)):
                    with self.assertRaises(ModelUnavailable):
                        client._http('gemini-3.5-flash-lite', 'countTokens', {})
            finally:
                client.close()

    def test_calls_accounted_and_context_cache_reused(self):
        calls = []
        def transport(model, operation, body):
            calls.append(operation)
            if operation == 'countTokens':
                return {'totalTokens': 100}
            payload = {'facts': [], 'unresolved': ['Unreadable document']}
            return {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(payload)}]}}],
                    'usageMetadata': {'promptTokenCount': 100, 'candidatesTokenCount': 20}}
        with tempfile.TemporaryDirectory() as folder:
            client = GeminiExtractor(Path(folder), transport=transport, day_key=lambda _: '2026-09-12')
            try:
                source = Source('message_x', 'message', 'user_x', '', '', '', 'Unclear text', {})
                self.assertEqual('unresolved', client.extract(source, 'gemini-3.5-flash-lite')['status'])
                client.extract(source, 'gemini-3.5-flash-lite')
                self.assertEqual(['countTokens', 'generateContent'], calls)
                self.assertEqual(1, client.cache_hits)
                self.assertEqual(2, len(client.usage))
            finally:
                client.close()

    def test_invalid_fresh_response_is_preserved_only_as_diagnostic(self):
        def transport(model,operation,body):
            if operation=='countTokens':
                return {'totalTokens':10}
            invalid={'facts':[{'type':'informational','scope':'informational','amount':'','currency':'',
                'effective_date':'','settlement_date':'','recurrence':'unknown','source_identity':'message_x',
                'quote':'Invented quote','uncertainty':''}],'unresolved':[]}
            return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(invalid)}]}}]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=Source('message_x','message','u','','','','Text',{})
            client=GeminiExtractor(root,transport=transport)
            try:
                from buy_or_wait.gemini import EvidenceBlocked
                with self.assertRaises(EvidenceBlocked):
                    client.extract(source,'gemini-3.5-flash-lite')
                self.assertEqual(1,len(list(root.glob('*.invalid-*.json'))))
                self.assertFalse((root/f'{cache_key(source,"gemini-3.5-flash-lite")}.json').exists())
            finally:
                client.close()

    def test_valid_preserved_diagnostic_is_recovered_without_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=Source('message_x','message','u','','','','Text',{})
            key=cache_key(source,'gemini-3.5-flash-lite')
            fact={'type':'informational','scope':'informational','amount':'','currency':'',
                  'effective_date':'','settlement_date':'','recurrence':'unknown',
                  'source_identity':'employer name','quote':'Text','uncertainty':''}
            (root/f'{key}.invalid-1.json').write_text(json.dumps({'facts':[fact],'unresolved':[]}),encoding='utf-8')
            client=GeminiExtractor(root,transport=lambda *args:(_ for _ in ()).throw(AssertionError('network called')))
            try:
                result=client.extract(source,'gemini-3.5-flash-lite')
                self.assertEqual('message_x',result['facts'][0]['source_identity'])
                self.assertEqual(1,client.cache_hits)
            finally:
                client.close()

    def test_quota_persists_across_client_instances(self):
        caps = {'gemini-3.5-flash-lite': (1, 250000, 1000)}
        clock = lambda: datetime(2026, 9, 13, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            for first in (True, False):
                client = GeminiExtractor(Path(folder), transport=lambda *args: {}, clock=clock,
                                         day_key=lambda _: '2026-09-12', caps=caps)
                try:
                    if first:
                        client._reserve('gemini-3.5-flash-lite', 10, 'countTokens')
                    else:
                        with self.assertRaises(QuotaBlocked):
                            client._reserve('gemini-3.5-flash-lite', 10, 'countTokens')
                finally:
                    client.close()

    def test_run_budget_blocks_before_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            client = GeminiExtractor(Path(folder), transport=lambda *args: {}, max_calls=1,
                                     day_key=lambda _: '2026-09-12')
            try:
                client._reserve('gemini-3.5-flash-lite', 10, 'countTokens')
                with self.assertRaises(QuotaBlocked):
                    client._reserve('gemini-3.6-flash', 10, 'countTokens')
            finally:
                client.close()

    def test_tpm_limit_checked_before_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            client = GeminiExtractor(Path(folder), transport=lambda *args: {}, day_key=lambda _: '2026-09-12')
            try:
                with self.assertRaises(QuotaBlocked):
                    client._reserve('gemini-3.5-flash-lite', 250001, 'generateContent')
            finally:
                client.close()


if __name__ == '__main__':
    unittest.main()
