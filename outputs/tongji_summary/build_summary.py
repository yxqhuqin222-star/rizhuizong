import json
from pathlib import Path

import pandas as pd


ROOT = Path("/Users/kityhello/workplace/project/rizhuizong")
DEMO_INPUT = ROOT / "tongji_demo.xlsx"
TARGET_INPUT = ROOT / "tongji_target.xlsx"
OUT_DIR = ROOT / "outputs" / "tongji_summary"

DEMO_SHEET = "rizhuizong_city (17)"
TARGET_SHEET = "Sheet1"
DEMO_REQUIRED_COLUMNS = [
    "下单日期",
    "成单量",
    "年级",
    "学部",
    "期次",
    "价体",
    "线索渠道二级分类",
    "last_from",
]
TARGET_REQUIRED_COLUMNS = [
    "期次",
    "线索渠道二级分类",
    "价体",
    "学部",
    "年级",
    "目标",
    "target_time",
    "进量日期",
]
DIMENSIONS = [
    "学部",
    "期次",
    "线索渠道二级分类",
    "价体",
    "年级",
]
GRADE_ORDER = {
    "小学": {
        "二年级": 1,
        "三年级": 2,
        "四年级": 3,
        "五年级": 4,
        "六年级": 5,
    },
    "初中": {
        "初一": 1,
        "初二": 2,
        "初三": 3,
    },
    "高中": {
        "高一": 1,
        "高二": 2,
        "高三": 3,
    },
}
TOTAL_DAYS = 6


def validate_columns(df, required_columns, label):
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"{label} 缺少必要字段: {', '.join(missing)}")


def normalize_channel(value):
    if isinstance(value, str) and value.startswith("外部微转-"):
        return "外部微转-*"
    return value


def calculate_progress(row):
    if pd.isna(row["target_time"]) or pd.isna(row["进量日期"]):
        return pd.NA

    elapsed_days = (pd.Timestamp.today().normalize() - row["进量日期"]).days
    progress = elapsed_days / TOTAL_DAYS
    return max(0, min(progress, 1))


def aggregate_current(df):
    data = df.copy()
    data["线索渠道二级分类"] = data["线索渠道二级分类"].map(normalize_channel)
    data["下单日期"] = pd.to_datetime(data["下单日期"], errors="coerce").dt.normalize()
    return (
        data.groupby(DIMENSIONS, dropna=False, as_index=False)
        .agg(现状=("成单量", "sum"), 下单日期=("下单日期", "max"))
    )


def aggregate_target(df):
    data = df.copy()
    data["线索渠道二级分类"] = data["线索渠道二级分类"].map(normalize_channel)
    data["target_time"] = pd.to_datetime(data["target_time"], errors="coerce").dt.normalize()
    data["进量日期"] = pd.to_datetime(data["进量日期"], errors="coerce").dt.normalize()
    return (
        data.groupby(DIMENSIONS, dropna=False, as_index=False)
        .agg(目标=("目标", "sum"), target_time=("target_time", "max"), 进量日期=("进量日期", "max"))
    )


def build_summary(demo, target):
    validate_columns(demo, DEMO_REQUIRED_COLUMNS, "demo")
    validate_columns(target, TARGET_REQUIRED_COLUMNS, "target")
    current_summary = aggregate_current(demo)
    target_summary = aggregate_target(target)

    summary = (
        target_summary.merge(current_summary, on=DIMENSIONS, how="outer")
        .fillna({"目标": 0, "现状": 0})
    )
    summary["年级顺序"] = summary.apply(
        lambda row: GRADE_ORDER.get(row["学部"], {}).get(
            row["年级"],
            len(GRADE_ORDER.get(row["学部"], {})) + 1,
        ),
        axis=1,
    )
    summary = (
        summary.sort_values(
            ["学部", "期次", "线索渠道二级分类", "价体", "年级顺序", "年级"],
            kind="stable",
        )
        .drop(columns="年级顺序")
    )
    summary["目标"] = summary["目标"].astype(int)
    summary["现状"] = summary["现状"].astype(int)
    summary["差距"] = summary["现状"] - summary["目标"]
    summary["完成率"] = summary.apply(
        lambda row: row["现状"] / row["目标"] if row["目标"] else pd.NA,
        axis=1,
    )
    summary["进度"] = summary.apply(calculate_progress, axis=1)
    summary["下单日期"] = summary["下单日期"].dt.strftime("%Y-%m-%d")
    summary["target_time"] = summary["target_time"].dt.strftime("%Y-%m-%d")
    summary["进量日期"] = summary["进量日期"].dt.strftime("%Y-%m-%d")
    summary = summary[
        DIMENSIONS + ["下单日期", "target_time", "进量日期", "目标", "现状", "差距", "完成率", "进度"]
    ]
    return summary, current_summary, target_summary


def latest_term_rows(summary, target_summary):
    def term_key(value):
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        return int(digits) if digits else -1

    target_terms = target_summary[["学部", "期次"]].drop_duplicates().copy()
    target_terms["term_rank"] = target_terms["期次"].map(term_key)
    latest_terms = target_terms.loc[
        target_terms["term_rank"].eq(target_terms.groupby("学部")["term_rank"].transform("max")),
        ["学部", "期次"],
    ].drop_duplicates()
    return summary.merge(latest_terms, on=["学部", "期次"], how="inner")


def frame_to_payload(df):
    return {
        "headers": list(df.columns),
        "rows": df.astype(object).where(pd.notna(df), None).values.tolist(),
    }


def metrics_for(df):
    target_total = int(df["目标"].sum())
    current_total = int(df["现状"].sum())
    progress_values = pd.to_numeric(df["进度"], errors="coerce")
    completion_values = pd.to_numeric(df["完成率"], errors="coerce").fillna(0)
    behind = df[progress_values.notna() & completion_values.lt(progress_values)]
    return {
        "target_total": target_total,
        "current_total": current_total,
        "completion": current_total / target_total if target_total else None,
        "avg_progress": float(progress_values.dropna().mean()) if progress_values.notna().any() else None,
        "behind_count": int(len(behind)),
        "row_count": int(len(df)),
    }


def write_outputs(summary, current_summary, target_summary, demo, target, out_dir=OUT_DIR):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_dir / "tongji_summary_current.csv", index=False, encoding="utf-8-sig")
    latest_summary = latest_term_rows(summary, target_summary)
    latest_terms = (
        latest_summary[["学部", "期次"]]
        .drop_duplicates()
        .sort_values(["学部", "期次"], kind="stable")
    )
    latest_terms_text = "；".join(
        f"{row['学部']}={row['期次']}" for _, row in latest_terms.iterrows()
    )

    dist_tables = {}
    for col in DIMENSIONS:
        dist = (
            latest_summary.groupby(col, dropna=False, as_index=False)[["目标", "现状"]]
            .sum()
            .sort_values(["现状", "目标"], ascending=False, kind="stable")
        )
        dist_tables[col] = dist
        dist.to_csv(out_dir / f"distribution_{col}.csv", index=False, encoding="utf-8-sig")

    metadata = pd.DataFrame(
        [
            ["现状原始行数", len(demo)],
            ["目标原始行数", len(target)],
            ["聚合组合数", len(summary)],
            ["目标合计", int(summary["目标"].sum())],
            ["现状合计", int(summary["现状"].sum())],
            ["完成率整体", summary["现状"].sum() / summary["目标"].sum() if summary["目标"].sum() else pd.NA],
            ["默认展示口径", "以 target 表中的期次为准，每个学部仅展示目标表里的最新期次；demo-only 期次保留在完整 Summary 中"],
            ["最新期次范围", latest_terms_text],
            ["最新期次聚合组合数", len(latest_summary)],
            ["最新期次目标合计", int(latest_summary["目标"].sum())],
            ["最新期次现状合计", int(latest_summary["现状"].sum())],
            [
                "最新期次完成率整体",
                latest_summary["现状"].sum() / latest_summary["目标"].sum()
                if latest_summary["目标"].sum()
                else pd.NA,
            ],
            ["总天数", TOTAL_DAYS],
            ["下单日期口径", "每个统计项下取 demo 最近一次下单日期，仅用于现状日期参考"],
            ["进量日期口径", "每个统计项下取 target 表中的进量日期"],
            ["进度计算", "进度=(当前日期-进量日期)/总天数，并限制在 0%-100%"],
            ["播报图期次口径", "以 target 表中的期次为准，小学、初中、高中各自仅播报目标表里的最新一期次数据"],
            ["播报图渠道展示", "线索渠道二级分类 + 价体"],
            ["播报图招生目标", "目标"],
            ["播报图剩余天数", "总天数-(target_time-进量日期)"],
            ["成单量最小值", int(demo["成单量"].min())],
            ["成单量最大值", int(demo["成单量"].max())],
            ["渠道归并规则", "线索渠道二级分类以“外部微转-”开头的值统一归为“外部微转-*”"],
            ["缺失值检查", "两个底表的指定维度字段及数值字段均无缺失"],
        ],
        columns=["指标", "值"],
    )
    metadata.to_csv(out_dir / "metadata.csv", index=False, encoding="utf-8-sig")

    payload = {
        "summary": frame_to_payload(summary),
        "latest_summary": frame_to_payload(latest_summary),
        "metrics": {
            "all": metrics_for(summary),
            "latest": metrics_for(latest_summary),
        },
        "metadata": frame_to_payload(metadata),
        "distributions": {
            name: frame_to_payload(table)
            for name, table in dist_tables.items()
        },
    }
    (out_dir / "summary_payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def read_inputs(demo_path=DEMO_INPUT, target_path=TARGET_INPUT):
    demo = pd.read_excel(demo_path, sheet_name=DEMO_SHEET)
    target = pd.read_excel(target_path, sheet_name=TARGET_SHEET)
    return demo, target


def rebuild(demo_path=DEMO_INPUT, target_path=TARGET_INPUT, out_dir=OUT_DIR):
    demo, target = read_inputs(demo_path, target_path)
    summary, current_summary, target_summary = build_summary(demo, target)
    payload = write_outputs(summary, current_summary, target_summary, demo, target, out_dir)
    return summary, payload


def main() -> None:
    summary, _payload = rebuild()

    print(f"summary_rows={len(summary)}")
    print(f"target_total={int(summary['目标'].sum())}")
    print(f"current_total={int(summary['现状'].sum())}")
    print(f"output={OUT_DIR / 'tongji_summary_current.csv'}")


if __name__ == "__main__":
    main()
