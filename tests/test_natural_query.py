import unittest

import pandas as pd

import app


class NaturalQueryTest(unittest.TestCase):
    def setUp(self):
        self.yzy = "out_wxst_wxstqt_1774944753086"
        self.demo = pd.DataFrame(
            [
                {
                    "下单日期": "2026-06-27",
                    "成单量": 1,
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
