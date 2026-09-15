import sys
import unittest
from datetime import date
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buy_or_wait.recurrence import infer_cadence, occurrence_dates, expense_estimate
from buy_or_wait.contracts import ContractError


class RecurrenceTests(unittest.TestCase):
    def test_monthly_is_not_thirty_days(self):
        dates = [date(2026,m,15) for m in (1,2,3)]
        c = infer_cadence(dates)
        self.assertEqual('monthly', c.kind)
        self.assertEqual([date(2026,4,15),date(2026,5,15)], list(occurrence_dates(c,after=dates[-1],through=date(2026,5,15))))

    def test_month_end_clamping(self):
        dates = [date(2025,12,31),date(2026,1,31),date(2026,2,28)]
        c = infer_cadence(dates)
        self.assertEqual([date(2026,3,31),date(2026,4,30)],list(occurrence_dates(c,after=dates[-1],through=date(2026,4,30))))

    def test_weekly_with_supported_jitter(self):
        dates = [date(2026,1,d) for d in (1,8,15,22,28)]
        c = infer_cadence(dates)
        self.assertEqual(('days',7),(c.kind,c.interval))
        self.assertEqual([date(2026,2,4)],list(occurrence_dates(c,after=dates[-1],through=date(2026,2,4))))

    def test_sparse_irregular_and_duplicate_rejected(self):
        for days in ((1,8),(1,8,8),(1,2,25,30)):
            self.assertIsNone(infer_cadence([date(2026,1,d) for d in days]))

    def test_explicit_estimators(self):
        values = [D('10'),D('11'),D('12'),D('20')]
        for policy, expected in [('latest','20'),('mean','13.25'),('p75','12'),('maximum','20')]:
            self.assertEqual(D(expected),expense_estimate(values,policy=policy))
        with self.assertRaises(ContractError):
            expense_estimate(values,policy='guess')


if __name__ == '__main__':
    unittest.main()
