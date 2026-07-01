import unittest

import pandas as pd

from reports.build_daily_report_images import progress_gap, remaining_days, render_rows


class RemainingDaysTest(unittest.TestCase):
    def test_uses_target_and_intake_dates_excluding_first_day(self):
        self.assertEqual(
            remaining_days(pd.Timestamp("2026-07-01"), pd.Timestamp("2026-06-25")),
            "1",
        )

    def test_missing_date_has_no_value(self):
        self.assertEqual(remaining_days(pd.NaT, pd.Timestamp("2026-06-25")), "--")


class ProgressGapTest(unittest.TestCase):
    def test_positive_gap_when_time_progress_is_ahead(self):
        self.assertAlmostEqual(progress_gap(0.48, 0.83), 0.35)

    def test_negative_gap_when_enrollment_progress_is_ahead(self):
        self.assertAlmostEqual(progress_gap(1.35, 0.83), -0.17)

    def test_negative_gap_is_rendered_with_its_sign(self):
        rendered = render_rows([{"进度GAP": -0.17}], ["进度GAP"])
        self.assertIn("-17%", rendered)


if __name__ == "__main__":
    unittest.main()
