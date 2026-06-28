import unittest
from datetime import datetime
from unittest.mock import patch

import pandas as pd

import app


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 6, 28, tzinfo=tz)


class NaturalQueryTest(unittest.TestCase):
    def setUp(self):
        self.yzy = "out_wxst_wxstqt_1774944753086"
        self.demo = pd.DataFrame(
            [
                {
                    "下单日期": "2026-06-27",
                    "成单量": 1,
                    "坐席姓名": "小王",
                    "年级": "高一",
                    "学部": "高中",
                    "期次": "暑_11",
                    "价体": 990,
                    "线索渠道二级分类": "LEC内测",
                    "last_from": self.yzy,
                },
                {
                    "下单日期": "2026-06-27",
                    "成单量": 2,
                    "坐席姓名": "小李",
                    "年级": "高二",
                    "学部": "高中",
                    "期次": "暑_11",
                    "价体": 990,
                    "线索渠道二级分类": "LEC内测",
                    "last_from": self.yzy,
                },
                {
                    "下单日期": "2026-06-26",
                    "成单量": 4,
                    "年级": "高一",
                    "学部": "高中",
                    "期次": "暑_11",
                    "价体": 990,
                    "线索渠道二级分类": "LEC内测",
                    "last_from": self.yzy,
                },
                {
                    "下单日期": "2026-06-27",
                    "成单量": 5,
                    "年级": "高一",
                    "学部": "高中",
                    "期次": "暑_11",
                    "价体": 990,
                    "线索渠道二级分类": "LLM外呼",
                    "last_from": "out_llm_a",
                },
                {
                    "下单日期": "2026-06-27",
                    "成单量": 7,
                    "年级": "高二",
                    "学部": "高中",
                    "期次": "暑_11",
                    "价体": 990,
                    "线索渠道二级分类": "LLM外呼",
                    "last_from": "out_llm_b",
                },
                {
                    "下单日期": "2026-06-27",
                    "成单量": 11,
                    "年级": "高三",
                    "学部": "高中",
                    "期次": "暑_11",
                    "价体": 100,
                    "线索渠道二级分类": "LLM外呼",
                    "last_from": "out_llm_c",
                },
            ]
        )
        self.target = pd.DataFrame(
            [
                {
                    "期次": "暑_11",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 990,
                    "学部": "高中",
                    "年级": "高一",
                    "目标": 100,
                    "target_time": "2026-07-02",
                    "进量日期": "2026-06-27",
                },
                {
                    "期次": "暑_11",
                    "线索渠道二级分类": "图书微转",
                    "价体": 100,
                    "学部": "高中",
                    "年级": "高一",
                    "目标": 150,
                    "target_time": "2026-07-02",
                    "进量日期": "2026-06-27",
                },
                {
                    "期次": "暑_8",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "学部": "小学",
                    "年级": "三年级",
                    "目标": 50,
                    "target_time": "2026-07-01",
                    "进量日期": "2026-06-27",
                },
            ]
        )

    def test_channel_alias_without_date_asks_for_time_range(self):
        result = app.run_natural_query("我们YZY渠道的进量", demo=self.demo, export_path=None)

        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["question"], "你想查询哪个时间段的？")
        self.assertEqual(result["context"]["last_from"], self.yzy)
        self.assertEqual(result["context"]["channel_name"], "LEC内测YZY")

    def test_follow_up_date_completes_pending_query(self):
        first = app.run_natural_query("我们YZY渠道的进量", demo=self.demo, export_path=None)
        result = app.run_natural_query(
            "6月27日",
            context=first["context"],
            page=1,
            page_size=10,
            demo=self.demo,
            export_path=None,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["matchedRows"], 2)
        self.assertEqual(result["conditions"]["date"], "2026-06-27")
        self.assertEqual(result["conditions"]["channelName"], "LEC内测YZY")
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["totalPages"], 1)
        self.assertEqual(len(result["rows"]), 2)

    def test_original_last_from_query_still_works(self):
        result = app.run_natural_query(
            f"6月27日，{self.yzy} 的成单量是多少？",
            demo=self.demo,
            export_path=None,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["conditions"]["last_from"], self.yzy)

    def test_metric_defaults_to_order_count(self):
        result = app.run_natural_query(
            "6月27日YZY渠道",
            demo=self.demo,
            export_path=None,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["conditions"]["metric"], "成单量")

    def test_yesterday_llm_9_9_query_aggregates_matching_channel_and_payment(self):
        with patch.object(app, "datetime", FixedDatetime):
            result = app.run_natural_query(
                "昨天llm9.9的单量",
                demo=self.demo,
                export_path=None,
            )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["total"], 12)
        self.assertEqual(result["matchedRows"], 2)
        self.assertEqual(result["conditions"]["date"], "2026-06-27")
        self.assertEqual(result["conditions"]["channelName"], "LLM外呼")
        self.assertEqual(result["conditions"]["payment"], 990)

    def test_secondary_channel_value_is_loaded_from_demo_knowledge(self):
        with patch.object(app, "datetime", FixedDatetime):
            result = app.run_natural_query(
                "昨天lec内测的总计单量",
                demo=self.demo,
                target=self.target,
                export_path=None,
            )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["conditions"]["filters"]["线索渠道二级分类"], "LEC内测")

    def test_target_only_dimension_value_is_recognized_for_default_metric(self):
        result = app.run_natural_query(
            "6月27日图书微转的单量",
            demo=self.demo,
            target=self.target,
            export_path=None,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["conditions"]["filters"]["线索渠道二级分类"], "图书微转")

    def test_explicit_target_metric_uses_target_rows(self):
        result = app.run_natural_query(
            "图书微转的目标",
            demo=self.demo,
            target=self.target,
            export_path=None,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["total"], 150)
        self.assertEqual(result["conditions"]["metric"], "目标")
        self.assertEqual(result["matchedRows"], 1)

    def test_multiple_dynamic_dimensions_are_combined(self):
        result = app.run_natural_query(
            "6月27日高中暑11 LEC内测990价体的单量",
            demo=self.demo,
            target=self.target,
            export_path=None,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["total"], 3)
        self.assertEqual(
            result["conditions"]["filters"],
            {
                "学部": "高中",
                "期次": "暑_11",
                "线索渠道二级分类": "LEC内测",
                "价体": 990,
            },
        )

    def test_demo_only_low_cardinality_field_is_queryable(self):
        result = app.run_natural_query(
            "6月27日小王的单量",
            demo=self.demo,
            target=self.target,
            export_path=None,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["conditions"]["filters"]["坐席姓名"], "小王")

    def test_three_departments_query_returns_breakdown_and_total(self):
        demo = pd.concat(
            [
                self.demo,
                pd.DataFrame(
                    [
                        {
                            "下单日期": "2026-06-26",
                            "成单量": 10,
                            "年级": "三年级",
                            "学部": "小学",
                            "期次": "暑_8",
                            "价体": 100,
                            "线索渠道二级分类": "LEC内测",
                            "last_from": self.yzy,
                        },
                        {
                            "下单日期": "2026-06-26",
                            "成单量": 20,
                            "年级": "初一",
                            "学部": "初中",
                            "期次": "暑_10",
                            "价体": 100,
                            "线索渠道二级分类": "LEC内测",
                            "last_from": self.yzy,
                        },
                    ]
                ),
            ],
            ignore_index=True,
        )

        result = app.run_natural_query(
            "6月26日，小学高三个学部分别的总单量",
            demo=demo,
            target=self.target,
            export_path=None,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["total"], 34)
        self.assertEqual(
            result["breakdown"],
            [
                {"label": "小学", "value": 10},
                {"label": "初中", "value": 20},
                {"label": "高中", "value": 4},
            ],
        )
        self.assertEqual(result["conditions"]["groupBy"], "学部")
        self.assertNotIn("年级", result["conditions"]["filters"])

    def test_literal_primary_high_three_query_keeps_grade_filter(self):
        result = app.run_natural_query(
            "6月27日小学高三的单量",
            demo=self.demo,
            target=self.target,
            export_path=None,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["conditions"]["filters"]["学部"], "小学")
        self.assertEqual(result["conditions"]["filters"]["年级"], "高三")
        self.assertNotIn("groupBy", result["conditions"])

    def test_unknown_channel_is_not_guessed(self):
        result = app.run_natural_query("6月27日这个渠道的进量", demo=self.demo, export_path=None)

        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["question"], "你想查询哪个渠道？")

    def test_multiple_channel_aliases_are_not_guessed(self):
        result = app.run_natural_query("6月27日YZY和JJ渠道的进量", demo=self.demo, export_path=None)

        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["question"], "检测到多个渠道，你想查询哪一个？")

    def test_all_configured_channel_names_resolve(self):
        aliases, names_by_code = app.load_channel_aliases()

        self.assertEqual(len(names_by_code), 6)
        self.assertEqual(names_by_code[self.yzy], "LEC内测YZY")
        self.assertIn(
            ("yzy", self.yzy, "LEC内测YZY"),
            aliases,
        )


if __name__ == "__main__":
    unittest.main()
