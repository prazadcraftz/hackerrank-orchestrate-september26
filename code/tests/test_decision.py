import sys,unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buy_or_wait.decision import installment_eligible,DecisionBlocked

class DecisionTests(unittest.TestCase):
    def test_monthly_payment_count_duration(self):
        profile={'max_installment_months':'3'}
        self.assertTrue(installment_eligible({'number_of_payments':'3','payment_frequency_days':'31'},profile))
        self.assertFalse(installment_eligible({'number_of_payments':'4','payment_frequency_days':'28'},profile))
        with self.assertRaises(DecisionBlocked):
            installment_eligible({'number_of_payments':'2','payment_frequency_days':'14'},profile)

if __name__=='__main__': unittest.main()
