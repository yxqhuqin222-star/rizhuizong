from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path("/Users/kityhello/workplace/project/rizhuizong")
SUMMARY_PATH = ROOT / "outputs" / "tongji_summary" / "tongji_summary_current.xlsx"
DEMO_PATH = ROOT / "tongji_demo.xlsx"
OUT_DIR = ROOT / "reports" / "daily_progress"
TOTAL_DAYS = 6
DEPARTMENTS = ["小学", "初中", "高中"]
GRADE_ORDER = {
    "二年级": 1,
    "三年级": 2,
    "四年级": 3,
    "五年级": 4,
    "六年级": 5,
    "初一": 1,
    "初二": 2,
    "初三": 3,
    "高一": 1,
    "高二": 2,
    "高三": 3,
}
LEC1_CHANNELS = [
    ("YZY", "086", 0.35),
    ("WC", "661", 0.25),
    ("RQ", "540", 0.19),
    ("JJ", "967", 0.11),
    ("SH", "158", 0.03),
    ("JS", "969", 0.07),
]


def term_key(value):
    match = re.search(r"(\d+)", str(value))
    return int(match.group(1)) if match else -1


def pct(value):
    if pd.isna(value):
        return None
    return max(0, min(float(value), 1))


def pct_text(value):
    value = pct(value)
    if value is None:
        return "--"
    return f"{value * 100:.0f}%"


def int_text(value):
    if pd.isna(value):
        return "--"
    return f"{int(round(float(value))):,}"


def channel_label(row):
    channel = str(row["线索渠道二级分类"])
    payment = row["价体"]
    if pd.isna(payment):
        return channel
    return f"{channel}-{int(payment)}元"


def gap_abs(progress, time_progress):
    if pd.isna(progress) or pd.isna(time_progress):
        return None
    return abs(float(progress) - float(time_progress))


def status_text(target, current, completion, time_progress):
    target = 0 if pd.isna(target) else float(target)
    current = 0 if pd.isna(current) else float(current)
    completion = 0 if pd.isna(completion) else float(completion)
    if target > 0 and current == 0:
        return "未开单"
    if not pd.isna(time_progress) and completion < float(time_progress):
        return "落后"
    if target > 0 and completion >= 1:
        return "已完成"
    if target == 0 and current > 0:
        return "仅现状"
    if not pd.isna(time_progress) and completion - float(time_progress) + 1e-9 >= 0.1:
        return "快"
    return "正常"


def remaining_days(target_time, intake_date):
    if pd.isna(target_time) or pd.isna(intake_date):
        return "--"
    elapsed_days = (
        pd.Timestamp(target_time).normalize() - pd.Timestamp(intake_date).normalize()
    ).days - 1
    return str(max(0, TOTAL_DAYS - elapsed_days))


def normalize_summary_frame(df):
    data = df.copy()
    for col in ["目标", "现状", "完成率", "进度"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    for col in ["下单日期", "target_time", "进量日期"]:
        data[col] = pd.to_datetime(data[col], errors="coerce")
    return data


def enrich(df):
    data = df.copy()
    data["渠道展示"] = data.apply(channel_label, axis=1)
    data["进度GAP"] = data.apply(lambda row: gap_abs(row["完成率"], row["进度"]), axis=1)
    data["剩余天数"] = data.apply(
        lambda row: remaining_days(row["target_time"], row["进量日期"]),
        axis=1,
    )
    return data


def aggregate_channel(df):
    grouped = (
        df.groupby(["期次", "渠道展示"], dropna=False, as_index=False)
        .agg(
            招生目标=("目标", "sum"),
            成单量=("现状", "sum"),
            target_time=("target_time", "max"),
            进量日期=("进量日期", "max"),
            进度=("进度", "max"),
        )
    )
    grouped["量级GAP"] = grouped["成单量"] - grouped["招生目标"]
    grouped["招生进度"] = grouped.apply(
        lambda row: row["成单量"] / row["招生目标"] if row["招生目标"] else pd.NA,
        axis=1,
    )
    grouped["状态"] = grouped.apply(
        lambda row: status_text(row["招生目标"], row["成单量"], row["招生进度"], row["进度"]),
        axis=1,
    )
    grouped["进度GAP"] = grouped.apply(lambda row: gap_abs(row["招生进度"], row["进度"]), axis=1)
    grouped["剩余天数"] = grouped.apply(
        lambda row: remaining_days(row["target_time"], row["进量日期"]),
        axis=1,
    )
    return grouped.sort_values(["期次", "渠道展示"], kind="stable")


def aggregate_grade(df):
    grouped = (
        df.groupby(["期次", "渠道展示", "年级"], dropna=False, as_index=False)
        .agg(
            招生目标=("目标", "sum"),
            成单量=("现状", "sum"),
            target_time=("target_time", "max"),
            进量日期=("进量日期", "max"),
            进度=("进度", "max"),
        )
    )
    grouped["量级GAP"] = grouped["成单量"] - grouped["招生目标"]
    grouped["招生进度"] = grouped.apply(
        lambda row: row["成单量"] / row["招生目标"] if row["招生目标"] else pd.NA,
        axis=1,
    )
    grouped["状态"] = grouped.apply(
        lambda row: status_text(row["招生目标"], row["成单量"], row["招生进度"], row["进度"]),
        axis=1,
    )
    grouped["进度GAP"] = grouped.apply(lambda row: gap_abs(row["招生进度"], row["进度"]), axis=1)
    grouped["剩余天数"] = grouped.apply(
        lambda row: remaining_days(row["target_time"], row["进量日期"]),
        axis=1,
    )
    grouped["年级顺序"] = grouped["年级"].map(GRADE_ORDER).fillna(len(GRADE_ORDER) + 1)
    return (
        grouped.sort_values(["期次", "渠道展示", "年级顺序", "年级"], kind="stable")
        .drop(columns="年级顺序")
    )


def bar(value, color, label=None):
    value = pct(value)
    if value is None:
        return '<span class="muted">--</span>'
    width = max(1, round(value * 100))
    safe_label = label if label is not None else f"{value * 100:.0f}%"
    return f'<div class="bar"><span style="width:{width}%; background:{color};"></span><b>{safe_label}</b></div>'


def render_rows(rows, columns):
    rendered = []
    for row in rows:
        cells = []
        for col in columns:
            value = row.get(col)
            if col in ["招生目标", "成单量", "量级GAP"]:
                cells.append(f'<td class="num">{int_text(value)}</td>')
            elif col == "招生进度":
                cells.append(f'<td>{bar(value, "#25b66a")}</td>')
            elif col == "时间进度":
                cells.append(f'<td>{bar(row.get("进度"), "#ff8a00")}</td>')
            elif col == "进度GAP":
                cells.append(f'<td>{bar(value, "#5b8ff9", pct_text(value))}</td>')
            elif col == "状态":
                text = "--" if pd.isna(value) else html.escape(str(value))
                cls = {
                    "未开单": "empty",
                    "落后": "late",
                    "已完成": "done",
                    "仅现状": "current-only",
                    "快": "normal",
                    "正常": "normal",
                }.get(str(value), "normal")
                cells.append(f'<td><span class="status {cls}">{text}</span></td>')
            else:
                text = "--" if pd.isna(value) else html.escape(str(value))
                cells.append(f"<td>{text}</td>")
        rendered.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(rendered)


def total_row(df, span_cols):
    target = df["招生目标"].sum()
    current = df["成单量"].sum()
    progress = current / target if target else pd.NA
    time_progress = df["进度"].dropna().max() if df["进度"].notna().any() else pd.NA
    gap = current - target
    progress_gap = gap_abs(progress, time_progress)
    target_time = df["target_time"].dropna().max() if df["target_time"].notna().any() else pd.NaT
    intake_date = df["进量日期"].dropna().max() if df["进量日期"].notna().any() else pd.NaT
    return {
        "期次": "总计",
        "渠道展示": "--",
        "年级": "--",
        "招生目标": target,
        "成单量": current,
        "量级GAP": gap,
        "招生进度": progress,
        "进度": time_progress,
        "状态": status_text(target, current, progress, time_progress),
        "进度GAP": progress_gap,
        "剩余天数": remaining_days(target_time, intake_date),
        "_span_cols": span_cols,
    }


def table_html(title, rows, columns):
    headers = "".join(f"<th>{html.escape(col)}</th>" for col in columns)
    body = render_rows(rows, columns)
    return f"""
      <section class="card">
        <h2>{html.escape(title)}</h2>
        <table>
          <thead><tr>{headers}</tr></thead>
          <tbody>{body}</tbody>
        </table>
      </section>
    """


LEC1_TERM = "暑_8"


def latest_target_term(df):
    target_basis = df[df["target_time"].notna()]
    terms = sorted(target_basis["期次"].dropna().unique(), key=term_key)
    return terms[-1] if terms else None


def render_lec1_share(demo):
    data = demo[
        demo["学部"].eq("小学")
        & demo["期次"].eq(LEC1_TERM)
        & pd.to_numeric(demo["价体"], errors="coerce").isin([1, 100])
    ].copy()
    data["last3"] = data["last_from"].astype(str).str[-3:]
    totals = data.groupby("last3")["成单量"].sum()

    counts = [int(totals.get(last3, 0)) for _name, last3, _target_share in LEC1_CHANNELS]
    total = sum(counts)
    actual_shares = [count / total if total else 0 for count in counts]
    target_shares = [target_share for _name, _last3, target_share in LEC1_CHANNELS]
    names = [name for name, _last3, _target_share in LEC1_CHANNELS]
    last_forms = [last3 for _name, last3, _target_share in LEC1_CHANNELS]

    def cells(values, formatter, extra_class=""):
        rendered = []
        for index, value in enumerate(values):
            classes = []
            if extra_class:
                classes.append(extra_class)
            if names[index] == "RQ":
                classes.append("highlight")
            class_attr = f' class="{" ".join(classes)}"' if classes else ""
            rendered.append(f"<td{class_attr}>{formatter(value)}</td>")
        return "".join(rendered)

    headers = "".join(f"<th>{html.escape(name)}</th>" for name in ["1元渠道"] + names + ["合计"])
    rows = [
        "<tr><th>成单量</th>"
        + cells(counts, int_text, "num")
        + f'<td class="num">{int_text(total)}</td></tr>',
        "<tr><th>目标占比</th>"
        + cells(target_shares, pct_text)
        + "<td>100%</td></tr>",
        "<tr><th>实际占比</th>"
        + cells(actual_shares, pct_text)
        + f"<td>{pct_text(1 if total else 0)}</td></tr>",
        "<tr><th>lastform</th>"
        + cells(last_forms, lambda value: html.escape(str(value)))
        + "<td></td></tr>",
    ]

    title = "lec1元占比播报"
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="report.css">
</head>
<body>
  <main class="report lec1-report">
    <header>
      <div>
        <h1>{html.escape(title)}</h1>
        <p>范围：小学 · {html.escape(LEC1_TERM)} · 1元 · 生成日期：{pd.Timestamp.today().strftime("%Y-%m-%d")}</p>
      </div>
      <div class="metrics">
        <div><span>渠道合计</span><b>{int_text(total)}</b></div>
        <div><span>渠道数</span><b>{len(LEC1_CHANNELS)}</b></div>
      </div>
    </header>
    <section class="card lec1-card">
      <table class="lec1-table">
        <thead><tr>{headers}</tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""
    html_path = OUT_DIR / "lec1_share.html"
    html_path.write_text(html_text, encoding="utf-8")
    return {
        "dept": "lec1",
        "term": LEC1_TERM,
        "html": str(html_path),
        "png": str(OUT_DIR / "lec1_share.png"),
        "summary": {
            "范围": f"小学 {LEC1_TERM} 1元",
            "成单量": str(total),
            "实际占比": "；".join(f"{name}={pct_text(share)}" for name, share in zip(names, actual_shares)),
        },
    }


def render_department(dept, df):
    latest = latest_target_term(df)
    if latest is None:
        return None
    latest_df = enrich(df[df["期次"].eq(latest)])

    channel = aggregate_channel(latest_df)
    grade = aggregate_grade(latest_df)
    channel_rows = channel.to_dict("records") + [total_row(channel, 2)]
    grade_rows = grade.to_dict("records") + [total_row(grade, 3)]

    title = f"{dept}每日招生进度播报"
    date_text = pd.Timestamp.today().strftime("%Y-%m-%d")
    summary = {
        "目标": int(latest_df["目标"].sum()),
        "成单量": int(latest_df["现状"].sum()),
        "完成率": latest_df["现状"].sum() / latest_df["目标"].sum() if latest_df["目标"].sum() else pd.NA,
        "平均进度": latest_df["进度"].dropna().mean() if latest_df["进度"].notna().any() else pd.NA,
    }

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="report.css">
</head>
<body>
  <main class="report">
    <header>
      <div>
        <h1>{html.escape(title)}</h1>
        <p>期次：{html.escape(str(latest))} · 生成日期：{date_text}</p>
      </div>
      <div class="metrics">
        <div><span>目标</span><b>{int_text(summary["目标"])}</b></div>
        <div><span>成单量</span><b>{int_text(summary["成单量"])}</b></div>
        <div><span>完成率</span><b>{pct_text(summary["完成率"])}</b></div>
        <div><span>时间进度</span><b>{pct_text(summary["平均进度"])}</b></div>
      </div>
    </header>
    {table_html("招生进度-分期次渠道", channel_rows, ["期次", "渠道展示", "招生目标", "成单量", "量级GAP", "招生进度", "时间进度", "进度GAP", "剩余天数", "状态"])}
    {table_html("招生进度-分期次渠道年级", grade_rows, ["期次", "渠道展示", "年级", "招生目标", "成单量", "招生进度", "时间进度", "进度GAP", "剩余天数", "状态"])}
  </main>
</body>
</html>
"""
    file_slug = {"小学": "primary", "初中": "middle", "高中": "high"}[dept]
    html_path = OUT_DIR / f"{file_slug}_daily_progress.html"
    html_path.write_text(html_text, encoding="utf-8")
    return {
        "dept": dept,
        "term": latest,
        "html": str(html_path),
        "png": str(OUT_DIR / f"{file_slug}_daily_progress.png"),
        "summary": {key: json.dumps(value, ensure_ascii=False, default=str) for key, value in summary.items()},
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.css").write_text(CSS, encoding="utf-8")
    df = normalize_summary_frame(pd.read_excel(SUMMARY_PATH, sheet_name="目标现状对比", header=1))
    demo = pd.read_excel(DEMO_PATH, sheet_name="rizhuizong_city (17)")
    outputs = []
    for dept in DEPARTMENTS:
        dept_df = df[df["学部"].eq(dept)].copy()
        if dept_df.empty:
            continue
        output = render_department(dept, dept_df)
        if output:
            outputs.append(output)
    lec1_output = render_lec1_share(demo)
    if lec1_output:
        outputs.append(lec1_output)
    (OUT_DIR / "manifest.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


CSS = """
body {
  margin: 0;
  background: #eef1f4;
  color: #273349;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.report {
  width: 1240px;
  padding: 16px;
}

header, .card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(26, 39, 64, 0.08);
  border: 1px solid #e4e9f0;
}

header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 20px;
  margin-bottom: 14px;
}

h1 {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
}

p {
  margin: 6px 0 0;
  color: #69758a;
  font-size: 13px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, 110px);
  gap: 10px;
}

.metrics div {
  border: 1px solid #e2e8f0;
  border-radius: 7px;
  padding: 10px;
  background: #f8fafc;
}

.metrics span {
  display: block;
  color: #69758a;
  font-size: 12px;
}

.metrics b {
  display: block;
  margin-top: 4px;
  font-size: 20px;
}

.card {
  padding: 14px;
  margin-bottom: 14px;
}

h2 {
  margin: 0 0 10px;
  font-size: 16px;
}

table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 12px;
}

th {
  background: #22b66a;
  color: #fff;
  text-align: left;
  padding: 9px 10px;
  font-weight: 700;
  border-right: 1px solid rgba(255,255,255,0.35);
}

td {
  padding: 8px 10px;
  border: 1px solid #e4e9f0;
  background: #fff;
  vertical-align: middle;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

tbody tr:nth-child(even) td {
  background: #f5f7fa;
}

tbody tr:last-child td {
  background: #fffbe8;
  font-weight: 700;
}

.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.bar {
  position: relative;
  height: 18px;
  background: #edf2f7;
  overflow: hidden;
}

.bar span {
  display: block;
  height: 100%;
  opacity: 0.95;
}

.bar b {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: #17202a;
  font-weight: 600;
}

.muted {
  color: #98a4b3;
}

.status {
  display: inline-block;
  min-width: 42px;
  padding: 2px 7px;
  border-radius: 999px;
  font-weight: 700;
  text-align: center;
}

.status.empty {
  background: #fff1f2;
  color: #be123c;
}

.status.late {
  background: #fff7ed;
  color: #c2410c;
}

.status.done {
  background: #ecfdf3;
  color: #047857;
}

.status.current-only {
  background: #eef6ff;
  color: #1f5fbf;
}

.status.normal {
  background: #f1f5f9;
  color: #475569;
}

.lec1-report {
  width: 1272px;
  padding: 0;
  background: #fff;
}

.lec1-report header {
  margin: 0 0 10px;
  border-radius: 0;
  box-shadow: none;
}

.lec1-report .metrics {
  grid-template-columns: repeat(2, 120px);
}

.lec1-card {
  padding: 0;
  margin: 0;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}

.lec1-table {
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 28px;
  color: #111;
}

.lec1-table th,
.lec1-table td {
  height: 40px;
  padding: 1px 8px;
  border: 2px solid #111;
  text-align: center;
  background: #fff;
  font-weight: 500;
  white-space: nowrap;
}

.lec1-table thead th {
  background: #13aee3;
  color: #000;
  font-weight: 700;
}

.lec1-table tbody th {
  background: #fff;
  color: #111;
}

.lec1-table .num {
  text-align: center;
}

.lec1-table .highlight {
  background: #ffc400;
}
"""


if __name__ == "__main__":
    main()
