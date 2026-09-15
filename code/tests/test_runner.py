import sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buy_or_wait.runner import run_predictions


class RunnerTests(unittest.TestCase):
    def test_blocked_run_does_not_overwrite_output(self):
        data=SimpleNamespace(tables={'requests':[{'request_id':'r'}]},fingerprint=lambda:{'x':'y'})
        evidence={'issues':[{'request_id':'r','blocking':True,'reason':'missing'}]}
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'output.csv';output.write_text('VALID OLD',encoding='utf-8')
            trace=Path(folder)/'trace.json'
            result=run_predictions(data,evidence,output,trace,expense_policy='latest')
            self.assertEqual('VALID OLD',output.read_text(encoding='utf-8'))
            self.assertEqual('blocked',result['status'])
            self.assertTrue(trace.exists())

    def test_complete_run_publishes_atomically(self):
        data=SimpleNamespace(tables={'requests':[{'request_id':'r'}]},fingerprint=lambda:{'x':'y'})
        evidence={'issues':[]}
        row={'request_id':'r','amount_safe_to_pay':'0','affordability_status':'not_affordable',
             'recommended_payment_method':'not_recommended','payment_plan':'none',
             'earliest_date_for_full_payment':'','spending_changes_needed':'none','decision_explanation':'No safe plan.'}
        with tempfile.TemporaryDirectory() as folder, patch('buy_or_wait.runner.decide',return_value={'row':row,'trace':{}}):
            output=Path(folder)/'output.csv';trace=Path(folder)/'trace.json'
            result=run_predictions(data,evidence,output,trace,expense_policy='latest')
            self.assertEqual('validated',result['status'])
            self.assertIn('request_id,amount_safe_to_pay',output.read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
