import unittest

import pandas as pd

from reports.build_daily_report_images import (
    LEC1_CHANNELS,
    LEC1_CUTOFF,
    LEC1_TERM,
    channel_label,
    filter_lec1_data,
    progress_gap,
    remaining_days,
    render_rows,
    status_text,
)


class RemainingDaysTest(unittest.TestCase):
    def test_uses_six_day_progress_stage_and_keeps_one_day_minimum(self):
        self.assertEqual(remaining_days(1 / 6), "5")
        self.assertEqual(remaining_days(2 / 6), "4")
        self.assertEqual(remaining_days(5 / 6), "1")
        self.assertEqual(remaining_days(1), "1")

    def test_missing_date_has_no_value(self):
        self.assertEqual(remaining_days(pd.NA), "--")


class ProgressGapTest(unittest.TestCase):
    def test_positive_gap_when_time_progress_is_ahead(self):
        self.assertAlmostEqual(progress_gap(0.48, 0.83), 0.35)

    def test_negative_gap_when_enrollment_progress_is_ahead(self):
        self.assertAlmostEqual(progress_gap(1.35, 0.83), -0.17)

    def test_negative_gap_is_rendered_with_its_sign(self):
        rendered = render_rows([{"进度GAP": -0.17}], ["进度GAP"])
        self.assertIn("-17%", rendered)


class ChannelLabelTest(unittest.TestCase):
    def test_uses_formatted_payment_without_truncating_decimal(self):
        row = pd.Series({"线索渠道二级分类": "LLM外呼", "价体": 9.9})

        self.assertEqual(channel_label(row), "LLM外呼-9.9元")


class Lec1ChannelsTest(unittest.TestCase):
    def test_channel_order_codes_and_target_shares_match_confirmed_plan(self):
        self.assertEqual(
            LEC1_CHANNELS,
            [
                ("YZY", "out_wxst_wxstqt_1774944753086", 0.25),
                ("WC", "out_wxst_wxstqt_1774944782661", 0.15),
                ("RQ", "out_wxst_wxstqt_1774945025540", 0.20),
                ("JJ", "out_wxst_wxstqt_1774945094967", 0.08),
                ("SH", "out_wxst_wxstqt_1774944710158", 0.12),
                ("ZXC", "out_wxst_wxstqt_1781763514315", 0.05),
                ("微转", "out_wxst_wxstqt_1774945129110", 0.12),
                ("HFS", "out_wxst_wxstqt_1781763558917", 0.03),
                ("YD", "out_wxst_wxstqt_1766038527925", 0.00),
                ("爆量本地化", "out_wxst_wxstqt_1766038666197", 0.00),
            ],
        )
        self.assertAlmostEqual(sum(channel[2] for channel in LEC1_CHANNELS), 1.0)

    def test_scope_uses_confirmed_term_and_cutoff(self):
        demo = pd.DataFrame(
            [
                {"学部": "小学", "期次": "暑_10", "价体": 100, "支付时间": LEC1_CUTOFF},
                {"学部": "小学", "期次": "暑_10", "价体": 100, "支付时间": LEC1_CUTOFF + pd.Timedelta(seconds=1)},
                {"学部": "小学", "期次": "暑_8", "价体": 100, "支付时间": LEC1_CUTOFF},
            ]
        )

        result = filter_lec1_data(demo)

        self.assertEqual(LEC1_TERM, "暑_10")
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["支付时间"], LEC1_CUTOFF)


class StatusTextTest(unittest.TestCase):
    def test_current_only_row_is_not_marked_behind(self):
        self.assertEqual(status_text(0, 1, pd.NA, 2 / 3), "仅现状")

    def test_zero_target_and_zero_current_is_not_marked_behind(self):
        self.assertEqual(status_text(0, 0, pd.NA, 2 / 3), "正常")


if __name__ == "__main__":
    unittest.main()
