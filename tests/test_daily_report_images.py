import unittest

import pandas as pd

from reports.build_daily_report_images import remaining_days


class RemainingDaysTest(unittest.TestCase):
    def test_uses_target_and_intake_dates_excluding_first_day(self):
        self.assertEqual(
            remaining_days(pd.Timestamp("2026-07-01"), pd.Timestamp("2026-06-25")),
            "1",
        )

    def test_missing_date_has_no_value(self):
        self.assertEqual(remaining_days(pd.NaT, pd.Timestamp("2026-06-25")), "--")


if __name__ == "__main__":
    unittest.main()
