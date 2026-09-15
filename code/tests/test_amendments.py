import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buy_or_wait.amendments import prepare_evidence


def event(i,description='Payroll credit',amount='100',status='settled',day='2026-01-15'):
    return {'event_id':f'e{i}','user_id':'u','event_type':'income','description':description,
            'category':'salary','direction':'credit','amount':amount,'currency':'EUR','event_date':day,
            'settlement_date':day,'status':status,'linked_event_id':'','flexibility':'fixed','minimum_allowed_amount':''}


def fact(**values):
    return {'source_id':'message_x','observed_at':'2026-03-01T00:00:00Z','related_event_id':'',
            'type':'salary_change','scope':'user','amount':'120','currency':'EUR','effective_date':'',
            'settlement_date':'','recurrence':'recurring','quote':'Your salary is EUR 120','uncertainty':''}|values


class AmendmentTests(unittest.TestCase):
    def test_recurring_salary_creates_deterministic_scheduled_event(self):
        events=[event(1,day='2026-01-15'),event(2,day='2026-02-15'),event(3,day='2026-03-15')]
        result=prepare_evidence(events,[fact()],request_date='2026-04-01',home_currency='EUR')
        created=result['events'][-1]
        self.assertEqual(('evidence:message_x:salary','120','2026-04-15'),
                         (created['event_id'],created['amount'],created['settlement_date']))

    def test_temporary_salary_returns_to_baseline(self):
        events=[event(1,amount='100',day='2026-01-15'),event(2,amount='100',day='2026-02-15'),
                event(3,amount='50',day='2026-03-15')]
        result=prepare_evidence(events,[fact(amount='70',recurrence='temporary')],request_date='2026-04-01',home_currency='EUR')
        self.assertEqual('100',str(result['salary_followup']['evidence:message_x:salary']))

    def test_percentage_rent_amendment(self):
        f=fact(type='amendment',amount='',currency='',recurrence='recurring',quote='Monthly rent increases by 12%.')
        result=prepare_evidence([event(1)],[f],request_date='2026-04-01',home_currency='EUR')
        self.assertEqual('1.12',str(result['expense_multipliers']['rent']))

    def test_future_evidence_not_visible(self):
        result=prepare_evidence([event(1)],[fact(observed_at='2027-01-01T00:00:00Z')],request_date='2026-04-01',home_currency='EUR')
        self.assertIsNone(result['salary_followup'].get('evidence:message_x:salary'))

    def test_cancellation_supersedes_scheduled_salary(self):
        events=[event(1),event(2,description='Next confirmed salary',status='scheduled',day='2026-04-15')]
        result=prepare_evidence(events,[fact(type='cancellation',amount='',currency='',recurrence='unknown',quote='The payroll contract has ended.')],request_date='2026-04-01',home_currency='EUR')
        self.assertEqual({'e2'},result['superseded'])
        self.assertTrue(result['suppress_historical_salary'])

    def test_foreign_salary_preserves_currency_for_dated_fx(self):
        f=fact(amount='200',currency='USD',settlement_date='2026-04-15')
        result=prepare_evidence([event(1)],[f],request_date='2026-04-01',home_currency='EUR')
        self.assertEqual('USD',result['events'][-1]['currency'])

    def test_confirmed_invoice_is_one_time_not_salary(self):
        f=fact(type='confirmation',scope='user',amount='300',currency='EUR',settlement_date='2026-04-20',
               recurrence='one_time',quote='The confirmed invoice payment settles on 2026-04-20.',source_type='service_provider')
        result=prepare_evidence([event(1)],[f],request_date='2026-04-01',home_currency='EUR')
        created=result['events'][-1]
        self.assertEqual(('other_income','scheduled'),(created['category'],created['status']))
        self.assertFalse(result['salary_followup'])

    def test_one_time_employer_arrears_do_not_replace_regular_salary(self):
        regular=fact(type='salary_change',amount='200',quote='Your regular salary is EUR 200.')
        arrears=fact(type='amount_fill',scope='user',amount='90',recurrence='one_time',
                     quote='The same payroll includes one-time arrears of EUR 90.',
                     source_type='employer')
        result=prepare_evidence([event(1)],[regular,arrears],request_date='2026-04-01',home_currency='EUR')
        self.assertEqual('200',result['events'][-1]['amount'])

    def test_cancelled_household_income_keeps_confirmed_replacement(self):
        cancel=fact(type='cancellation',amount='',currency='',quote='One household payroll has ended.')
        remaining=fact(type='salary_change',amount='80',quote='The remaining salary is EUR 80.')
        result=prepare_evidence([event(1)],[cancel,remaining],request_date='2026-04-01',home_currency='EUR')
        self.assertEqual('80',result['events'][-1]['amount'])
        self.assertFalse(result['suppress_historical_salary'])

    def test_linked_amount_fill_only_fills_blank_event(self):
        blank=event(1,amount='')
        f=fact(type='amount_fill',scope='event',related_event_id='e1',amount='45',
               quote='The final amount is EUR 45.',recurrence='one_time')
        result=prepare_evidence([blank],[f],request_date='2026-04-01',home_currency='EUR')
        self.assertEqual('45',result['events'][0]['amount'])
        self.assertEqual('fill_event_amount',result['trace'][0]['action'])

    def test_dated_confirmation_marks_pending_credit_confirmed(self):
        pending=event(1,status='pending',day='2026-04-10')
        f=fact(type='confirmation',scope='event',related_event_id='e1',amount='',
               settlement_date='2026-04-12',quote='The credit will settle on 2026-04-12.',
               recurrence='one_time')
        result=prepare_evidence([pending],[f],request_date='2026-04-01',home_currency='EUR')
        self.assertEqual({'e1'},result['confirmed_credit_ids'])
        self.assertEqual('2026-04-12',result['events'][0]['settlement_date'])

    def test_dated_delay_revives_failed_debit_as_scheduled(self):
        failed=event(1,status='failed',day='2026-04-02')
        failed['direction'],failed['category'],failed['event_type']='debit','utilities','debt_payment'
        f=fact(type='delay',scope='event',related_event_id='e1',amount='',
               settlement_date='2026-04-08',quote='Another debit will be attempted on 2026-04-08.',
               recurrence='one_time')
        result=prepare_evidence([failed],[f],request_date='2026-04-01',home_currency='EUR')
        self.assertEqual(('scheduled','2026-04-08'),
                         (result['events'][0]['status'],result['events'][0]['settlement_date']))


if __name__=='__main__':
    unittest.main()
