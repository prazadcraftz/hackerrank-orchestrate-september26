import sys
import unittest
from datetime import date,timedelta
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buy_or_wait.cashflow import CashState,Flow,replay
from buy_or_wait.changes import legal_actions,apply_actions,spending_change_candidates

DAY=date(2026,1,1)


def event(i,category='streaming',flexibility='stoppable',minimum=''):
    return {'event_id':f'e{i}','user_id':'u','category':category,'direction':'debit','amount':'30',
            'flexibility':flexibility,'minimum_allowed_amount':minimum}


def profile():
    return {'expense_categories_to_protect':'rent','expense_categories_user_is_willing_to_reduce':'streaming|shopping',
            'expense_categories_user_is_willing_to_stop':'streaming','payment_methods_user_will_consider':'full_payment',
            'max_installment_months':''}


def series(i,category='streaming',amount='30'):
    return {'kind':'expense','category':category,'anchor_event_id':f'e{i}','amount':amount,
            'projected_dates':['2026-01-02']}


class ChangeTests(unittest.TestCase):
    def test_protection_and_action_permissions(self):
        groups=legal_actions([series(1),series(2,'rent'),series(3,'shopping')],
                             [event(1),event(2,'rent'),event(3,'shopping','reducible','10')],profile())
        self.assertEqual([['stop:e1'],['reduce_to:e3:10']],[[a['serialized'] for a in g] for g in groups])

    def test_savings_begin_at_future_occurrence(self):
        state=CashState(DAY,DAY+timedelta(days=2),D('100'),D('20'),
                        (Flow('projected:e1:2026-01-02',DAY+timedelta(days=1),D('-30'),'recurring'),),'debits_first')
        changed,savings=apply_actions(state,[{'kind':'stop','event_id':'e1','value':D('0'),'serialized':'stop:e1'}],[series(1)])
        self.assertEqual(D('30'),savings)
        self.assertEqual(D('100'),replay(changed,[])['closing_balance'])

    def test_two_changes_can_unlock_full_plan(self):
        flows=(Flow('projected:e1:2026-01-02',DAY+timedelta(days=1),D('-30'),'recurring'),
               Flow('projected:e2:2026-01-03',DAY+timedelta(days=2),D('-30'),'recurring'))
        state=CashState(DAY,DAY+timedelta(days=4),D('100'),D('20'),flows,'debits_first')
        req={'request_id':'r','request_date':'2026-01-01','requested_amount':'70','desired_completion_date':'2026-01-05'}
        candidates=spending_change_candidates(state,req,profile(),[],[series(1),series(2)],
                                              [event(1),event(2)],installment_eligible=lambda o,p:True)
        self.assertEqual(('stop:e1','stop:e2'),candidates[0].changes)

    def test_never_more_than_three_changes(self):
        flows=tuple(Flow(f'projected:e{i}:2026-01-02',DAY+timedelta(days=1),D('-10'),'recurring') for i in range(4))
        state=CashState(DAY,DAY+timedelta(days=2),D('100'),D('20'),flows,'debits_first')
        req={'request_id':'r','request_date':'2026-01-01','requested_amount':'80','desired_completion_date':'2026-01-03'}
        self.assertFalse(spending_change_candidates(state,req,profile(),[],[series(i,amount='10') for i in range(4)],
                                                    [event(i) for i in range(4)],installment_eligible=lambda o,p:True))


if __name__=='__main__':
    unittest.main()
