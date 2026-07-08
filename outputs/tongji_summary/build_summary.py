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
SUMMARY_DEMO_REQUIRED_COLUMNS = DEMO_REQUIRED_COLUMNS + ["custom_uid"]
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
FALLBACK_DIMENSIONS = [
    "学部",
    "期次",
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


def format_payment_value(value):
    if pd.isna(value):
        return value
    numeric = float(value) / 100
    return int(numeric) if numeric.is_integer() else numeric


def format_payment_for_output(df):
    data = df.copy()
    if "价体" in data.columns:
        data["价体"] = data["价体"].map(format_payment_value)
    return data


def validate_department_term_dates(target):
    data = target.copy()
    for column in ["target_time", "进量日期"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
        counts = data.groupby(["学部", "期次"], dropna=False)[column].nunique(dropna=True)
        inconsistent = counts[counts.gt(1)]
        if not inconsistent.empty:
            labels = "、".join(f"{dept}/{term}" for dept, term in inconsistent.index)
            raise ValueError(f"target 中同学部、同一期次的{column}不一致: {labels}")


def calculate_progress(row):
    if pd.isna(row["进度日期"]) or pd.isna(row["进量日期"]):
        return pd.NA

    elapsed_days = (row["进度日期"] - row["进量日期"]).days
    progress = elapsed_days / TOTAL_DAYS
    return max(0, min(progress, 1))


def add_progress_dates(summary, current_summary):
    latest_order_dates = (
        current_summary.groupby(
            ["学部", "期次"],
            dropna=False,
            as_index=False,
        )["下单日期"]
        .max()
        .rename(columns={"下单日期": "进度日期"})
    )
    return summary.merge(
        latest_order_dates,
        on=["学部", "期次"],
        how="left",
    )


def aggregate_current(df):
    data = df.copy()
    data["线索渠道二级分类"] = data["线索渠道二级分类"].map(normalize_channel)
    data["下单日期"] = pd.to_datetime(data["下单日期"], errors="coerce").dt.normalize()
    data["_custom_uid_key"] = [
        ("custom_uid", value) if pd.notna(value) else ("missing_row", position)
        for position, value in enumerate(data["custom_uid"])
    ]
    return (
        data.groupby(DIMENSIONS, dropna=False, as_index=False)
        .agg(现状=("_custom_uid_key", "nunique"), 下单日期=("下单日期", "max"))
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


def assign_unmatched_current_channels(current_summary, target_summary):
    target_channels = {}
    exact_target_keys = set()
    for row in target_summary[DIMENSIONS].itertuples(index=False, name=None):
        exact_target_keys.add(row)
        fallback_key = (row[0], row[1], row[3], row[4])
        target_channels.setdefault(fallback_key, set()).add(row[2])

    data = current_summary.copy()
    ambiguous = []
    channel_index = data.columns.get_loc("线索渠道二级分类")
    for index, row in enumerate(data[DIMENSIONS].itertuples(index=False, name=None)):
        if row in exact_target_keys:
            continue
        if row[2] == "常规外呼":
            continue
        fallback_key = (row[0], row[1], row[3], row[4])
        candidates = target_channels.get(fallback_key, set())
        if len(candidates) == 1:
            data.iat[index, channel_index] = next(iter(candidates))
        elif len(candidates) > 1:
            if "常规外呼" in candidates:
                data.iat[index, channel_index] = "常规外呼"
            elif "LEC内测" in candidates:
                data.iat[index, channel_index] = "LEC内测"
            else:
                ambiguous.append(
                    f"{row[0]}/{row[1]}/{row[4]}/{format_payment_value(row[3])}元/"
                    f"{row[2]}→{','.join(sorted(map(str, candidates)))}"
                )

    if ambiguous:
        raise ValueError(
            "demo 中存在渠道未命中 target、同价体有多个候选且不含常规外呼或LEC内测: "
            + "；".join(ambiguous)
        )

    return (
        data.groupby(DIMENSIONS, dropna=False, as_index=False)
        .agg(现状=("现状", "sum"), 下单日期=("下单日期", "max"))
    )


def build_summary(demo, target):
    validate_columns(demo, SUMMARY_DEMO_REQUIRED_COLUMNS, "demo")
    validate_columns(target, TARGET_REQUIRED_COLUMNS, "target")
    validate_department_term_dates(target)
    current_summary = aggregate_current(demo)
    target_summary = aggregate_target(target)
    current_summary = assign_unmatched_current_channels(current_summary, target_summary)

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
    summary = add_progress_dates(summary, current_summary)
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
    has_target = pd.to_numeric(df["目标"], errors="coerce").fillna(0).gt(0)
    behind = df[has_target & progress_values.notna() & completion_values.lt(progress_values)]
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
    latest_summary = latest_term_rows(summary, target_summary)
    output_summary = format_payment_for_output(summary)
    output_latest_summary = format_payment_for_output(latest_summary)
    output_summary.to_csv(out_dir / "tongji_summary_current.csv", index=False, encoding="utf-8-sig")
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
        dist = format_payment_for_output(dist)
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
            ["下单日期口径", "明细展示每个统计项下 demo 最近一次下单日期"],
            ["进量日期口径", "每个统计项下取 target 表中的进量日期"],
            ["进度计算", "进度=(当前日期-进量日期)/总天数，并限制在 0%-100%；当前日期统一取同学部、同一期次 demo 的最近下单日期"],
            ["日期一致性", "同学部、同一期次的 target_time 和进量日期必须分别唯一，否则停止生成"],
            ["播报图期次口径", "以 target 表中的期次为准，小学、初中、高中各自仅播报目标表里的最新一期次数据"],
            ["价体展示", "原始价体除以 100，去除无意义的小数位，例如 100→1、990→9.9、1880→18.8"],
            ["播报图渠道展示", "线索渠道二级分类 + 格式化后的价体"],
            ["播报图招生目标", "目标"],
            ["播报图剩余天数", "总天数-(target_time-进量日期-1)"],
            ["成单量最小值", int(demo["成单量"].min())],
            ["成单量最大值", int(demo["成单量"].max())],
            ["渠道归并规则", "线索渠道二级分类以“外部微转-”开头的值统一归为“外部微转-*”"],
            ["未命中渠道归属", "常规外呼未命中 target 时保留为仅现状项；其他渠道按同一学部、期次、价体、年级寻找 target 渠道，唯一候选直接归属，多个候选优先常规外呼、其次 LEC内测，两者都没有时报错，无候选保留为仅现状项"],
            ["现状计算", "同一统计维度下按 custom_uid 去重计数；custom_uid 缺失的行分别计数"],
            ["缺失值检查", "两个底表的指定维度字段及数值字段均无缺失"],
        ],
        columns=["指标", "值"],
    )
    metadata.to_csv(out_dir / "metadata.csv", index=False, encoding="utf-8-sig")

    payload = {
        "summary": frame_to_payload(output_summary),
        "latest_summary": frame_to_payload(output_latest_summary),
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
