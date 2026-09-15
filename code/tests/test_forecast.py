import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buy_or_wait.cashflow import capacity
from buy_or_wait.forecast import build_forecast, is_regular_salary


def profile():
    return {'home_currency':'EUR','current_available_balance':'1000','minimum_balance_to_keep':'100'}


def request():
    return {'request_id':'r','user_id':'u','request_date':'2026-04-01','requested_amount':'500'}


def event(i, day, amount='100', direction='debit', category='rent', description='Monthly rent', status='settled'):
    return {'event_id':f'e{i}','user_id':'u','event_type':'income' if direction=='credit' else 'expense',
            'description':description,'category':category,'direction':direction,'amount':amount,'currency':'EUR',
            'event_date':day,'settlement_date':day,'status':status,'linked_event_id':'','flexibility':'fixed',
            'minimum_allowed_amount':''}


class ForecastTests(unittest.TestCase):
    def test_confirmed_next_salary_establishes_monthly_anchor(self):
        events=[event(1,'2026-03-15','50','credit','salary','Prorated first salary'),
                event(2,'2026-04-15','200','credit','salary','Next confirmed salary','scheduled')]
        result=build_forecast(events,profile(),request(),{})
        salary=[f for f in result['state'].flows if f.amount>0]
        self.assertEqual([date(2026,4,15),date(2026,5,15),date(2026,6,15)],[f.day for f in salary])

    def test_final_payroll_stops_old_series(self):
        events=[event(i,f'2026-0{i}-15','200','credit','salary','Payroll credit') for i in (1,2,3)]
        events.append(event(4,'2026-03-20','200','credit','salary','Final employer payroll'))
        self.assertFalse(any(f.amount>0 for f in build_forecast(events,profile(),request(),{})['state'].flows))

    def test_separate_parallel_salary_series_not_averaged(self):
        events=[]
        for i,month in enumerate((1,2,3)):
            events += [event(i,f'2026-0{month}-15','200','credit','salary','Primary household salary'),
                       event(i+10,f'2026-0{month}-20',str(80+i*10),'credit','salary','Second household income')]
        result=build_forecast(events,profile(),request(),{})
        income=[s for s in result['series_trace'] if s['kind']=='income']
        self.assertEqual({'Primary household salary','Second household income'},{s['description'] for s in income})
        self.assertEqual({'200','80'},{s['amount'] for s in income})

    def test_variable_expense_max_six_and_explicit_date_replacement(self):
        events=[event(i,f'2026-03-{i+1:02}','10') for i in range(6)]
        # Daily unsupported because cadence interval one is below allowed range.
        self.assertFalse(build_forecast(events,profile(),request(),{})['series_trace'])

    def test_regular_salary_classifier_excludes_unsupported_income(self):
        self.assertTrue(is_regular_salary('Payroll credit'))
        for value in ('Final employer payroll','Quarterly bonus','Platform payout','Client invoice',
                      'Freelance milestone payment','Independent work payment',
                      'Client retainer payment','Seasonal contract payment'):
            self.assertFalse(is_regular_salary(value))

    def test_projected_foreign_salary_uses_each_dated_rate(self):
        events=[event(1,'2026-03-15','100','credit','salary','Prorated first salary'),
                event(2,'2026-04-15','200','credit','salary','Next confirmed salary','scheduled')]
        for item in events:
            item['currency']='USD'
        rates={(f'2026-0{month}-15','USD','EUR'):str(month) for month in (4,5,6)}
        result=build_forecast(events,profile(),request(),rates)
        self.assertEqual(['800','1000','1200'],[str(f.amount) for f in result['state'].flows if f.amount>0])


if __name__=='__main__':
    unittest.main()
