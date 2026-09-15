import json,sys,tempfile,unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buy_or_wait.usage import summarize_usage,summarize_ledger,render_usage

class UsageTests(unittest.TestCase):
    def test_deduplicates_and_prices_generation_metadata(self):
        record={'model':'gemini-3.5-flash-lite','operation':'generateContent',
                'time':'2026-01-02T00:00:00+00:00','status':'ok',
                'usage':{'promptTokenCount':1000,'candidatesTokenCount':100,
                         'thoughtsTokenCount':200,'totalTokenCount':1300}}
        with tempfile.TemporaryDirectory() as folder:
            a=Path(folder)/'a.json';b=Path(folder)/'b.json'
            a.write_text(json.dumps({'usage_this_run':[record],'cache_hits_previous_runs':2,
                                     'cache_hits_this_run':0}),encoding='utf-8')
            b.write_text(json.dumps({'usage_this_run':[record],'cache_hits_this_run':1}),encoding='utf-8')
            result=summarize_usage([a,b],evaluation_requests=10)
            item=result['per_model']['gemini-3.5-flash-lite']
            self.assertEqual((1,1000,300,200),(item['api_calls'],item['input_tokens'],item['output_tokens'],item['thinking_tokens']))
            self.assertAlmostEqual(.001*.30+.0003*2.50,item['list_price_usd'])
            self.assertEqual(3,result['cache_hits'])
            self.assertIn('Average tokens per evaluation request: 130.00',render_usage(result))
            self.assertEqual(render_usage(result),render_usage(result))

    def test_ledger_cutoff_excludes_old_calls(self):
        old={'model':'gemini-3.5-flash-lite','operation':'generateContent',
             'time':'2026-01-01T00:00:00+00:00','status':'ok',
             'usage':{'promptTokenCount':1,'candidatesTokenCount':1,'totalTokenCount':2}}
        new=old|{'time':'2026-01-02T00:00:00+00:00'}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'usage.jsonl'
            path.write_text(json.dumps(old)+'\n'+json.dumps(new)+'\n',encoding='utf-8')
            result=summarize_ledger(path,since='2026-01-02T00:00:00Z')
            self.assertEqual(1,result['total']['api_calls'])

    def test_failed_generation_does_not_count_local_token_reservation(self):
        failed={'model':'gemini-3.5-flash-lite','operation':'generateContent',
                'time':'2026-01-02T00:00:00Z','status':'failed','reserved_input_tokens':999}
        good={'model':'gemini-3.5-flash-lite','operation':'generateContent',
              'time':'2026-01-02T00:00:01Z','status':'ok',
              'usage':{'promptTokenCount':10,'candidatesTokenCount':5,'totalTokenCount':15}}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'usage.jsonl'
            path.write_text(json.dumps(failed)+'\n'+json.dumps(good)+'\n',encoding='utf-8')
            result=summarize_ledger(path,since='2026-01-02T00:00:00Z')
            item=result['per_model']['gemini-3.5-flash-lite']
            self.assertEqual((2,1,10,5),(item['api_calls'],item['failed_calls'],
                                        item['input_tokens'],item['output_tokens']))

    def test_rejects_incomplete_or_inconsistent_success_metadata(self):
        base={'model':'gemini-3.6-flash','operation':'generateContent',
              'time':'2026-01-02T00:00:00Z','status':'ok'}
        records=[base|{'usage':{'promptTokenCount':10}},
                 base|{'usage':{'promptTokenCount':10,'candidatesTokenCount':5,
                                'totalTokenCount':16}}]
        for record in records:
            with self.subTest(record=record),tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'usage.jsonl'
                path.write_text(json.dumps(record)+'\n',encoding='utf-8')
                with self.assertRaises(ValueError):
                    summarize_ledger(path,since='2026-01-01T00:00:00Z')

    def test_rejects_unknown_model_inside_cutoff(self):
        old={'model':'retired-model','operation':'generateContent',
             'time':'2026-01-01T00:00:00Z','status':'failed'}
        unknown=old|{'time':'2026-01-02T00:00:00Z'}
        good={'model':'gemini-3.5-flash-lite','operation':'generateContent',
              'time':'2026-01-02T00:00:01Z','status':'ok',
              'usage':{'promptTokenCount':1,'candidatesTokenCount':1,'totalTokenCount':2}}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'usage.jsonl'
            path.write_text('\n'.join(map(json.dumps,(old,unknown,good)))+'\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'unknown model'):
                summarize_ledger(path,since='2026-01-02T00:00:00Z')

if __name__=='__main__':unittest.main()
