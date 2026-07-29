import unittest

import pandas as pd

from reports.build_daily_report_images import (
    LEC1_CHANNELS,
    channel_label,
    filter_lec1_data,
    lec1_actual_shares,
    lec1_channel_counts,
    latest_lec1_term,
    latest_target_term,
    progress_gap,
    remaining_days,
    render_rows,
    status_text,
    term_key,
)


class RemainingDaysTest(unittest.TestCase):
    def test_uses_six_day_progress_stage_and_keeps_one_day_minimum(self):
        self.assertEqual(remaining_days(1 / 6), "5")
        self.assertEqual(remaining_days(2 / 6), "4")
        self.assertEqual(remaining_days(5 / 6), "1")

    def test_target_day_has_zero_remaining_days(self):
        self.assertEqual(remaining_days(1), "0")

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


class LatestTermTest(unittest.TestCase):
    def test_latest_target_term_uses_confirmed_season_order(self):
        frame = pd.DataFrame(
            [
                {"期次": "暑_13", "target_time": "2026-07-21"},
                {"期次": "秋_1", "target_time": "2026-07-28"},
                {"期次": "春_99", "target_time": "2026-03-01"},
            ]
        )

        self.assertEqual(latest_target_term(frame), "秋_1")
        self.assertGreater(term_key("秋_1"), term_key("暑_13"))
        self.assertGreater(term_key("寒_1"), term_key("秋_99"))


class Lec1ChannelsTest(unittest.TestCase):
    def test_channel_order_codes_and_target_volumes_match_confirmed_plan(self):
        self.assertEqual(
            LEC1_CHANNELS,
            [
                ("YZY", "out_wxst_wxstqt_1774944753086", 4400, 0.54),
                ("WC", "out_wxst_wxstqt_1774944782661", 1800, 0.22),
                ("RQ", "out_wxst_wxstqt_1774945025540", 1000, 0.12),
                ("JJ", "out_wxst_wxstqt_1774945094967", 1000, 0.12),
            ],
        )
        self.assertEqual(sum(channel[2] for channel in LEC1_CHANNELS), 8200)

    def test_scope_matches_progress_summary_without_intake_cutoff(self):
        demo = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_12",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "下单日期": "2026-07-09",
                    "支付时间": "2026-07-10 10:00:00",
                    "custom_uid": "u1",
                    "last_from": "out_wxst_wxstqt_1774944753086",
                },
                {
                    "学部": "小学",
                    "期次": "暑_8",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "下单日期": "2026-07-09",
                    "支付时间": "2026-07-10 10:00:00",
                    "custom_uid": "u2",
                    "last_from": "out_wxst_wxstqt_1774944753086",
                },
                {
                    "学部": "小学",
                    "期次": "暑_11",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "下单日期": "2026-07-08",
                    "支付时间": "2026-07-08 10:00:00",
                    "custom_uid": "u3",
                    "last_from": "out_wxst_wxstqt_1774944753086",
                },
                {
                    "学部": "小学",
                    "期次": "暑_12",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 990,
                    "年级": "三年级",
                    "下单日期": "2026-07-08",
                    "支付时间": "2026-07-08 10:00:00",
                    "custom_uid": "u4",
                    "last_from": "out_wxst_wxstqt_1774944753086",
                },
            ]
        )
        target = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_11",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "目标": 100,
                    "target_time": "2026-07-15",
                    "进量日期": "2026-07-09",
                },
                {
                    "学部": "小学",
                    "期次": "暑_12",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "目标": 100,
                    "target_time": "2026-07-29",
                    "进量日期": "2026-07-23",
                },
            ]
        )

        result = filter_lec1_data(demo, target)

        self.assertEqual(latest_lec1_term(target), "暑_12")
        self.assertEqual(result["custom_uid"].tolist(), ["u1"])

    def test_intake_uses_order_volume_with_custom_uid_deduplication(self):
        demo = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_11",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "下单日期": "2026-07-09",
                    "custom_uid": "u1",
                    "last_from": "out_wxst_wxstqt_1774944753086",
                },
                {
                    "学部": "小学",
                    "期次": "暑_11",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "下单日期": "2026-07-09",
                    "custom_uid": "u1",
                    "last_from": "out_wxst_wxstqt_1774944753086",
                },
            ]
        )
        target = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_11",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "目标": 100,
                    "target_time": "2026-07-15",
                    "进量日期": "2026-07-09",
                },
            ]
        )

        result = filter_lec1_data(demo, target)
        counts = lec1_channel_counts(result)
        yzy_index = [name for name, _code, _target, _share in LEC1_CHANNELS].index("YZY")

        self.assertEqual(len(result), 2)
        self.assertEqual(counts[yzy_index], 1)

    def test_actual_share_uses_one_yuan_denominator(self):
        data = pd.DataFrame(
            [
                {"价体": 100, "custom_uid": "y1", "last_from": "out_wxst_wxstqt_1774944753086"},
                {"价体": 100, "custom_uid": "y2", "last_from": "out_wxst_wxstqt_1774944753086"},
                {"价体": 100, "custom_uid": "r1", "last_from": "out_wxst_wxstqt_1774945025540"},
                {"价体": 990, "custom_uid": "s1", "last_from": "out_wxst_wxstqt_1774944710158"},
            ]
        )

        shares = lec1_actual_shares(data)

        self.assertEqual(shares, [2 / 3, 0, 1 / 3, 0])


class StatusTextTest(unittest.TestCase):
    def test_current_only_row_is_not_marked_behind(self):
        self.assertEqual(status_text(0, 1, pd.NA, 2 / 3), "仅现状")

    def test_zero_target_and_zero_current_is_not_marked_behind(self):
        self.assertEqual(status_text(0, 0, pd.NA, 2 / 3), "正常")


if __name__ == "__main__":
    unittest.main()
