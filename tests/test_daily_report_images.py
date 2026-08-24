import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from reports.build_daily_report_images import (
    LEC1_CHANNELS,
    channel_label,
    filter_lec1_data,
    lec1_actual_shares,
    lec1_channel_counts,
    lec1_external_count,
    lec1_summary_scope,
    latest_lec1_term,
    latest_target_term,
    progress_gap,
    remaining_days,
    render_lec1_share,
    render_overall_progress,
    render_rows,
    status_text,
    term_key,
)


ROOT = Path(__file__).parents[1]


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
                ("YZY", "out_wxst_wxstqt_1774944753086", 2500, 0.45, [100]),
                ("WC", "out_wxst_wxstqt_1774944782661", 500, 0.09, [100]),
                ("RQ（9.9+1）", "out_wxst_wxstqt_1774945025540", 500, 0.09, [100, 990]),
                ("JJ", "out_wxst_wxstqt_1774945094967", 300, 0.05, [100]),
                ("SH", "out_wxst_wxstqt_1774944710158", 200, 0.04, [100]),
                ("ZXC", "out_wxst_wxstqt_1781763514315", 300, 0.05, [100]),
                ("ZH（9）", "out_wxst_wxstqt_1781763613827", 1000, 0.18, [900]),
            ],
        )
        self.assertEqual(sum(channel[2] for channel in LEC1_CHANNELS), 5300)
        self.assertEqual(sum(channel[3] for channel in LEC1_CHANNELS), 0.95)

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
        yzy_index = [name for name, _code, _target, _share, _payment_values in LEC1_CHANNELS].index("YZY")

        self.assertEqual(len(result), 2)
        self.assertEqual(counts[yzy_index], 1)

    def test_actual_share_uses_one_yuan_denominator_by_default(self):
        data = pd.DataFrame(
            [
                {"价体": 100, "custom_uid": "y1", "last_from": "out_wxst_wxstqt_1774944753086"},
                {"价体": 100, "custom_uid": "y2", "last_from": "out_wxst_wxstqt_1774944753086"},
                {"价体": 100, "custom_uid": "r1", "last_from": "out_wxst_wxstqt_1774945025540"},
                {"价体": 990, "custom_uid": "r2", "last_from": "out_wxst_wxstqt_1774945025540"},
                {"价体": 900, "custom_uid": "z1", "last_from": "out_wxst_wxstqt_1781763613827"},
                {"价体": 990, "custom_uid": "s1", "last_from": "out_wxst_wxstqt_1774944710158"},
            ]
        )

        shares = lec1_actual_shares(data)

        self.assertEqual(shares, [2 / 5, 0, 2 / 5, 0, 0, 0, 1 / 5])

    def test_render_lec1_share_excludes_channels_without_target_from_lec_scope(self):
        demo = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_12",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "下单日期": "2026-07-09",
                    "custom_uid": "known",
                    "last_from": "out_wxst_wxstqt_1774944753086",
                },
                {
                    "学部": "小学",
                    "期次": "暑_12",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "下单日期": "2026-07-09",
                    "custom_uid": "other",
                    "last_from": "unlisted-source",
                },
                {
                    "学部": "小学",
                    "期次": "暑_12",
                    "线索渠道二级分类": "外部微转-社群",
                    "价体": 100,
                    "年级": "三年级",
                    "下单日期": "2026-07-09",
                    "custom_uid": "external",
                    "last_from": "external-source",
                },
            ]
        )
        target = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_12",
                    "线索渠道二级分类": "LEC内测",
                    "价体": 100,
                    "年级": "三年级",
                    "目标": 8800,
                    "target_time": "2026-07-29",
                    "进量日期": "2026-07-23",
                },
            ]
        )
        summary = pd.DataFrame(
            [
                {
                    "学部": "小学",
                    "期次": "暑_12",
                    "线索渠道二级分类": "LEC内测",
                    "价体": "1.0",
                    "年级": "三年级",
                    "下单日期": "2026-07-09",
                    "target_time": "2026-07-29",
                    "进量日期": "2026-07-23",
                    "目标": 8800,
                    "现状": 2,
                    "完成率": 2 / 8800,
                    "进度": 0.5,
                },
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "reports.build_daily_report_images.OUT_DIR",
            Path(temp_dir),
        ):
            output = render_lec1_share(demo, target, summary)

        self.assertEqual(output["summary"]["报量"], "5500")
        self.assertEqual(output["summary"]["进量"], "2")
        self.assertIn("YZY=1", output["summary"]["渠道进量"])
        self.assertIn("外部微转=0", output["summary"]["渠道进量"])
        self.assertIn("未配置=1", output["summary"]["渠道进量"])

    def test_lec1_external_count_uses_raw_external_microtransfer_only(self):
        data = pd.DataFrame(
            [
                {"线索渠道二级分类": "外部微转-社群", "custom_uid": "e1"},
                {"线索渠道二级分类": "外部微转-图书", "custom_uid": "e2"},
                {"线索渠道二级分类": "LEC内测", "custom_uid": "unlisted"},
            ]
        )

        self.assertEqual(lec1_external_count(data), 2)

    def test_lec1_summary_scope_accepts_csv_and_xlsx_payment_formats(self):
        summary = pd.DataFrame(
            [
                {"学部": "小学", "期次": "暑_12", "线索渠道二级分类": "LEC内测", "价体": "1.0", "目标": 1, "现状": 1},
                {"学部": "小学", "期次": "暑_12", "线索渠道二级分类": "LEC内测", "价体": "1", "目标": 2, "现状": 2},
                {"学部": "小学", "期次": "暑_12", "线索渠道二级分类": "LEC内测", "价体": "9.9", "目标": 3, "现状": 3},
            ]
        )

        scoped = lec1_summary_scope(summary, "暑_12")

        self.assertEqual(scoped["目标"].sum(), 6)


class ArtifactConsistencyTest(unittest.TestCase):
    def test_render_overall_progress_uses_latest_department_metrics(self):
        summary = pd.DataFrame(
            [
                {"学部": "小学", "期次": "暑_1", "target_time": "2026-07-01", "目标": 10, "现状": 8, "进度": 1},
                {"学部": "小学", "期次": "暑_2", "target_time": "2026-07-08", "目标": 20, "现状": 25, "进度": 1},
                {"学部": "初中", "期次": "秋_1", "target_time": "2026-08-01", "目标": 30, "现状": 10, "进度": 0.5},
                {"学部": "高中", "期次": "秋_1", "target_time": "2026-08-01", "目标": 40, "现状": 20, "进度": 0.75},
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "reports.build_daily_report_images.OUT_DIR",
            Path(temp_dir),
        ):
            output = render_overall_progress(summary)

        self.assertEqual(output["dept"], "overall")
        self.assertIn("目标=20", output["summary"]["小学"])
        self.assertIn("现状=25", output["summary"]["小学"])
        self.assertIn("完成率=125.0%", output["summary"]["小学"])
        self.assertIn("平均进度=100%", output["summary"]["小学"])

    def test_csv_xlsx_and_manifest_share_current_summary_metrics(self):
        csv = pd.read_csv(ROOT / "outputs/tongji_summary/tongji_summary_current.csv")
        xlsx = pd.read_excel(
            ROOT / "outputs/tongji_summary/tongji_summary_current.xlsx",
            sheet_name="目标现状对比",
            header=1,
        )
        with (ROOT / "reports/daily_progress/manifest.json").open() as handle:
            manifest = {item["dept"]: item for item in json.load(handle)}

        self.assertEqual(len(csv), len(xlsx))
        self.assertEqual(int(csv["目标"].sum()), int(xlsx["目标"].sum()))
        self.assertEqual(int(csv["现状"].sum()), int(xlsx["现状"].sum()))

        overall = manifest["overall"]
        for department in ["小学", "初中", "高中"]:
            scoped = csv[csv["学部"].eq(department)]
            term = latest_target_term(scoped)
            latest = scoped[scoped["期次"].eq(term)]
            self.assertIn(f"目标={int(latest['目标'].sum()):,}", overall["summary"][department])
            self.assertIn(f"现状={int(latest['现状'].sum()):,}", overall["summary"][department])

        for dept in ["小学", "初中", "高中"]:
            item = manifest[dept]
            scoped = csv[csv["学部"].eq(dept) & csv["期次"].eq(item["term"])]
            target = int(scoped["目标"].sum())
            current = int(scoped["现状"].sum())
            progress = pd.to_numeric(scoped["进度"], errors="coerce")
            self.assertEqual(item["summary"]["目标"], str(target))
            self.assertEqual(item["summary"]["成单量"], str(current))
            self.assertEqual(
                item["summary"]["平均进度"],
                str(progress.dropna().mean()),
            )

        lec1 = manifest["lec1"]
        self.assertEqual(lec1["summary"]["报量"], "5500")
        self.assertIn("RQ（9.9+1）=", lec1["summary"]["渠道进量"])
        self.assertIn("ZH（9）=", lec1["summary"]["渠道进量"])


class StatusTextTest(unittest.TestCase):
    def test_current_only_row_is_not_marked_behind(self):
        self.assertEqual(status_text(0, 1, pd.NA, 2 / 3), "仅现状")

    def test_zero_target_and_zero_current_is_not_marked_behind(self):
        self.assertEqual(status_text(0, 0, pd.NA, 2 / 3), "正常")


if __name__ == "__main__":
    unittest.main()
