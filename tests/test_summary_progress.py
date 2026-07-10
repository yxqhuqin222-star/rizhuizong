import importlib.util
import unittest
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).parents[1] / "outputs" / "tongji_summary" / "build_summary.py"
SPEC = importlib.util.spec_from_file_location("build_summary", MODULE_PATH)
build_summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_summary)


class SummaryProgressTest(unittest.TestCase):
    def test_current_only_row_is_not_counted_as_behind(self):
        frame = pd.DataFrame(
            [
                {"目标": 0, "现状": 1, "完成率": pd.NA, "进度": 2 / 3},
                {"目标": 100, "现状": 50, "完成率": 0.5, "进度": 2 / 3},
            ]
        )

        self.assertEqual(build_summary.metrics_for(frame)["behind_count"], 1)

    def test_counts_distinct_custom_uid_within_each_summary_dimension(self):
        demo = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_9",
                    "线索渠道二级分类": "LLM外呼",
                    "价体": 990,
                    "年级": "三年级",
                    "custom_uid": 1001,
                    "成单量": 1,
                    "下单日期": "2026-07-02",
                },
                {
                    "学部": "小学",
                    "期次": "暑_9",
                    "线索渠道二级分类": "LLM外呼",
                    "价体": 990,
                    "年级": "三年级",
                    "custom_uid": 1001,
                    "成单量": 1,
                    "下单日期": "2026-07-03",
                },
                {
                    "学部": "小学",
                    "期次": "暑_9",
                    "线索渠道二级分类": "LLM外呼",
                    "价体": 990,
                    "年级": "三年级",
                    "custom_uid": 1002,
                    "成单量": 1,
                    "下单日期": "2026-07-03",
                },
            ]
        )

        result = build_summary.aggregate_current(demo)

        self.assertEqual(result.loc[0, "现状"], 2)
        self.assertEqual(result.loc[0, "下单日期"], pd.Timestamp("2026-07-03"))

    def test_counts_rows_separately_when_custom_uid_is_missing(self):
        demo = pd.DataFrame(
            [
                {
                    "学部": "初中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "常规外呼",
                    "价体": 100,
                    "年级": "初一",
                    "custom_uid": pd.NA,
                    "成单量": 1,
                    "下单日期": "2026-07-02",
                },
                {
                    "学部": "初中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "常规外呼",
                    "价体": 100,
                    "年级": "初一",
                    "custom_uid": pd.NA,
                    "成单量": 1,
                    "下单日期": "2026-07-03",
                },
            ]
        )

        result = build_summary.aggregate_current(demo)

        self.assertEqual(result.loc[0, "现状"], 2)

    def test_filters_current_rows_before_department_term_intake_date(self):
        demo = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_9",
                    "线索渠道二级分类": "LLM外呼",
                    "价体": 990,
                    "年级": "三年级",
                    "custom_uid": "before-intake",
                    "成单量": 1,
                    "下单日期": "2026-07-01",
                },
                {
                    "学部": "小学",
                    "期次": "暑_9",
                    "线索渠道二级分类": "LLM外呼",
                    "价体": 990,
                    "年级": "三年级",
                    "custom_uid": "on-intake",
                    "成单量": 1,
                    "下单日期": "2026-07-02",
                },
                {
                    "学部": "小学",
                    "期次": "暑_10",
                    "线索渠道二级分类": "LLM外呼",
                    "价体": 990,
                    "年级": "三年级",
                    "custom_uid": "demo-only-term",
                    "成单量": 1,
                    "下单日期": "2026-07-01",
                },
            ]
        )
        target = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_9",
                    "线索渠道二级分类": "LLM外呼",
                    "价体": 990,
                    "年级": "三年级",
                    "目标": 100,
                    "target_time": "2026-07-08",
                    "进量日期": "2026-07-02",
                }
            ]
        )

        result = build_summary.filter_current_by_intake_date(demo, target)

        self.assertEqual(result["custom_uid"].tolist(), ["on-intake", "demo-only-term"])

    def test_assigns_unmatched_channel_when_target_candidate_is_unique(self):
        current = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_8",
                    "线索渠道二级分类": "测试测试",
                    "价体": 100,
                    "年级": "三年级",
                    "现状": 7,
                    "下单日期": pd.Timestamp("2026-07-03"),
                },
                {
                    "学部": "小学",
                    "期次": "暑_8",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "现状": 5,
                    "下单日期": pd.Timestamp("2026-07-02"),
                },
            ]
        )
        target = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_8",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                }
            ]
        )

        result = build_summary.assign_unmatched_current_channels(current, target)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "线索渠道二级分类"], "LEC内测")
        self.assertEqual(result.loc[0, "现状"], 12)
        self.assertEqual(result.loc[0, "下单日期"], pd.Timestamp("2026-07-03"))

    def test_keeps_unmatched_regular_outbound_as_current_only(self):
        current = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_9",
                    "线索渠道二级分类": "常规外呼",
                    "价体": 990,
                    "年级": "三年级",
                    "现状": 7,
                    "下单日期": pd.Timestamp("2026-07-03"),
                }
            ]
        )
        target = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_9",
                    "线索渠道二级分类": "LLM外呼",
                    "价体": 990,
                    "年级": "三年级",
                }
            ]
        )

        result = build_summary.assign_unmatched_current_channels(current, target)

        self.assertEqual(result.loc[0, "线索渠道二级分类"], "常规外呼")
        self.assertEqual(result.loc[0, "现状"], 7)

    def test_prefers_regular_outbound_when_target_has_multiple_candidates(self):
        current = pd.DataFrame(
            [
                {
                    "学部": "高中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "测试测试",
                    "价体": 100,
                    "年级": "高一",
                    "现状": 7,
                    "下单日期": pd.Timestamp("2026-07-03"),
                }
            ]
        )
        target = pd.DataFrame(
            [
                {
                    "学部": "高中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "图书店铺",
                    "价体": 100,
                    "年级": "高一",
                },
                {
                    "学部": "高中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "常规外呼",
                    "价体": 100,
                    "年级": "高一",
                },
            ]
        )

        result = build_summary.assign_unmatched_current_channels(current, target)

        self.assertEqual(result.loc[0, "线索渠道二级分类"], "常规外呼")

    def test_prefers_lec_when_multiple_candidates_do_not_include_regular_outbound(self):
        current = pd.DataFrame(
            [
                {
                    "学部": "初中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "测试测试",
                    "价体": 990,
                    "年级": "初二",
                    "现状": 7,
                    "下单日期": pd.Timestamp("2026-07-03"),
                }
            ]
        )
        target = pd.DataFrame(
            [
                {
                    "学部": "初中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 990,
                    "年级": "初二",
                },
                {
                    "学部": "初中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "LLM外呼",
                    "价体": 990,
                    "年级": "初二",
                },
            ]
        )

        result = build_summary.assign_unmatched_current_channels(current, target)

        self.assertEqual(result.loc[0, "线索渠道二级分类"], "LEC内测")

    def test_rejects_multiple_candidates_without_preferred_channel(self):
        current = pd.DataFrame(
            [
                {
                    "学部": "高中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "测试测试",
                    "价体": 100,
                    "年级": "高一",
                    "现状": 7,
                    "下单日期": pd.Timestamp("2026-07-03"),
                }
            ]
        )
        target = pd.DataFrame(
            [
                {
                    "学部": "高中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "图书店铺",
                    "价体": 100,
                    "年级": "高一",
                },
                {
                    "学部": "高中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "外部微转-*",
                    "价体": 100,
                    "年级": "高一",
                },
            ]
        )

        with self.assertRaisesRegex(ValueError, "不含常规外呼或LEC内测"):
            build_summary.assign_unmatched_current_channels(current, target)
    def test_formats_payment_for_display_without_changing_source(self):
        source = pd.DataFrame({"价体": [0, 100, 990, 1880, 2880]})

        result = build_summary.format_payment_for_output(source)

        self.assertEqual(result["价体"].tolist(), [0, 1, 9.9, 18.8, 28.8])
        self.assertEqual(source["价体"].tolist(), [0, 100, 990, 1880, 2880])

    def test_counts_each_day_from_intake_date(self):
        row = pd.Series(
            {
                "下单日期": pd.Timestamp("2026-07-07"),
                "进量日期": pd.Timestamp("2026-07-02"),
                "target_time": pd.Timestamp("2026-07-08"),
                "进度日期": pd.Timestamp("2026-07-03"),
            }
        )

        self.assertAlmostEqual(build_summary.calculate_progress(row), 2 / 6)

    def test_counts_intake_date_as_first_progress_day(self):
        row = pd.Series(
            {
                "下单日期": pd.Timestamp("2026-07-08"),
                "进量日期": pd.Timestamp("2026-07-08"),
                "target_time": pd.Timestamp("2026-07-14"),
                "进度日期": pd.Timestamp("2026-07-08"),
            }
        )

        self.assertAlmostEqual(build_summary.calculate_progress(row), 1 / 6)

    def test_clamps_progress_to_zero_and_one(self):
        before_intake = pd.Series(
            {
                "下单日期": pd.Timestamp("2026-07-01"),
                "进量日期": pd.Timestamp("2026-07-03"),
                "target_time": pd.Timestamp("2026-07-09"),
                "进度日期": pd.Timestamp("2026-07-01"),
            }
        )
        after_period = pd.Series(
            {
                "下单日期": pd.Timestamp("2026-07-10"),
                "进量日期": pd.Timestamp("2026-07-02"),
                "target_time": pd.Timestamp("2026-07-08"),
                "进度日期": pd.Timestamp("2026-07-10"),
            }
        )

        self.assertEqual(build_summary.calculate_progress(before_intake), 0)
        self.assertEqual(build_summary.calculate_progress(after_period), 1)

    def test_missing_order_date_has_no_progress(self):
        row = pd.Series(
            {
                "下单日期": pd.NaT,
                "进量日期": pd.Timestamp("2026-07-02"),
                "target_time": pd.Timestamp("2026-07-08"),
                "进度日期": pd.NaT,
            }
        )

        self.assertTrue(pd.isna(build_summary.calculate_progress(row)))

    def test_all_rows_use_latest_department_term_order_date(self):
        summary = pd.DataFrame(
            [
                {
                    "学部": "初中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "LLM外呼",
                    "下单日期": pd.Timestamp("2026-06-27"),
                    "进量日期": pd.Timestamp("2026-07-01"),
                },
                {
                    "学部": "初中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "常规外呼",
                    "下单日期": pd.Timestamp("2026-06-30"),
                    "进量日期": pd.Timestamp("2026-07-01"),
                },
            ]
        )
        current_summary = pd.DataFrame(
            [
                {
                    "学部": "初中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "LLM外呼",
                    "下单日期": pd.Timestamp("2026-06-27"),
                },
                {
                    "学部": "初中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "常规外呼",
                    "下单日期": pd.Timestamp("2026-07-01"),
                },
            ]
        )

        summary["target_time"] = pd.Timestamp("2026-07-07")
        result = build_summary.add_progress_dates(summary, current_summary)

        self.assertEqual(result.loc[0, "下单日期"], pd.Timestamp("2026-06-27"))
        self.assertEqual(result.loc[0, "进度日期"], pd.Timestamp("2026-07-01"))
        self.assertEqual(result.loc[1, "进度日期"], pd.Timestamp("2026-07-01"))
        self.assertAlmostEqual(build_summary.calculate_progress(result.loc[0]), 1 / 6)
        self.assertAlmostEqual(build_summary.calculate_progress(result.loc[1]), 1 / 6)

    def test_department_term_without_order_date_has_no_progress(self):
        summary = pd.DataFrame(
            [
                {
                    "学部": "初中",
                    "期次": "暑_11",
                    "线索渠道二级分类": "LLM外呼",
                    "下单日期": pd.NaT,
                    "进量日期": pd.Timestamp("2026-07-01"),
                }
            ]
        )
        current_summary = summary[
            ["学部", "期次", "线索渠道二级分类", "下单日期"]
        ].copy()

        summary["target_time"] = pd.Timestamp("2026-07-07")
        result = build_summary.add_progress_dates(summary, current_summary)

        self.assertTrue(pd.isna(result.loc[0, "进度日期"]))
        self.assertTrue(pd.isna(build_summary.calculate_progress(result.loc[0])))

    def test_holds_at_five_sixths_until_target_date(self):
        base = {
            "下单日期": pd.Timestamp("2026-07-12"),
            "进量日期": pd.Timestamp("2026-07-08"),
            "target_time": pd.Timestamp("2026-07-14"),
        }

        day_five = pd.Series({**base, "进度日期": pd.Timestamp("2026-07-12")})
        day_before_target = pd.Series({**base, "进度日期": pd.Timestamp("2026-07-13")})
        target_day = pd.Series({**base, "进度日期": pd.Timestamp("2026-07-14")})

        self.assertAlmostEqual(build_summary.calculate_progress(day_five), 5 / 6)
        self.assertAlmostEqual(build_summary.calculate_progress(day_before_target), 5 / 6)
        self.assertEqual(build_summary.calculate_progress(target_day), 1)

    def test_rejects_conflicting_department_term_dates(self):
        target = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_8",
                    "target_time": "2026-07-01",
                    "进量日期": "2026-06-25",
                },
                {
                    "学部": "小学",
                    "期次": "暑_8",
                    "target_time": "2026-07-02",
                    "进量日期": "2026-06-25",
                },
            ]
        )

        with self.assertRaisesRegex(ValueError, "target_time不一致"):
            build_summary.validate_department_term_dates(target)


if __name__ == "__main__":
    unittest.main()
