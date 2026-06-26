from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path("/Users/kityhello/workplace/project/rizhuizong")
SUMMARY_PATH = ROOT / "outputs" / "tongji_summary" / "tongji_summary_current.xlsx"
OUT_DIR = ROOT / "reports" / "daily_progress"
TOTAL_DAYS = 6
DEPARTMENTS = ["小学", "初中", "高中"]


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


def elapsed_days(time_progress):
    if pd.isna(time_progress):
        return "--"
    return str(max(0, round(float(time_progress) * TOTAL_DAYS)))


def normalize_summary_frame(df):
    data = df.copy()
    for col in ["目标", "现状", "完成率", "进度"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    for col in ["下单日期", "target_time"]:
        data[col] = pd.to_datetime(data[col], errors="coerce")
    return data


def enrich(df):
    data = df.copy()
    data["渠道展示"] = data.apply(channel_label, axis=1)
    data["进度GAP"] = data.apply(lambda row: gap_abs(row["完成率"], row["进度"]), axis=1)
    data["剩余天数"] = data["进度"].apply(elapsed_days)
    return data


def aggregate_channel(df):
    grouped = (
        df.groupby(["期次", "渠道展示"], dropna=False, as_index=False)
        .agg(
            招生目标=("目标", "sum"),
            成单量=("现状", "sum"),
            target_time=("target_time", "max"),
            进度=("进度", "max"),
        )
    )
    grouped["量级GAP"] = grouped["成单量"] - grouped["招生目标"]
    grouped["招生进度"] = grouped.apply(
        lambda row: row["成单量"] / row["招生目标"] if row["招生目标"] else pd.NA,
        axis=1,
    )
    grouped["进度GAP"] = grouped.apply(lambda row: gap_abs(row["招生进度"], row["进度"]), axis=1)
    grouped["剩余天数"] = grouped["进度"].apply(elapsed_days)
    return grouped.sort_values(["期次", "渠道展示"], kind="stable")


def aggregate_grade(df):
    grouped = (
        df.groupby(["期次", "渠道展示", "年级"], dropna=False, as_index=False)
        .agg(
            招生目标=("目标", "sum"),
            成单量=("现状", "sum"),
            进度=("进度", "max"),
        )
    )
    grouped["量级GAP"] = grouped["成单量"] - grouped["招生目标"]
    grouped["招生进度"] = grouped.apply(
        lambda row: row["成单量"] / row["招生目标"] if row["招生目标"] else pd.NA,
        axis=1,
    )
    grouped["进度GAP"] = grouped.apply(lambda row: gap_abs(row["招生进度"], row["进度"]), axis=1)
    grouped["剩余天数"] = grouped["进度"].apply(elapsed_days)
    return grouped.sort_values(["期次", "渠道展示", "年级"], kind="stable")


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
    return {
        "期次": "总计",
        "渠道展示": "--",
        "年级": "--",
        "招生目标": target,
        "成单量": current,
        "量级GAP": gap,
        "招生进度": progress,
        "进度": time_progress,
        "进度GAP": progress_gap,
        "剩余天数": elapsed_days(time_progress),
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


def render_department(dept, df):
    target_basis = df[df["target_time"].notna()]
    terms = sorted(target_basis["期次"].dropna().unique(), key=term_key)
    if not terms:
        return None
    latest = terms[-1]
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
    {table_html("招生进度-分期次渠道", channel_rows, ["期次", "渠道展示", "招生目标", "成单量", "量级GAP", "招生进度", "时间进度", "进度GAP", "剩余天数"])}
    {table_html("招生进度-分期次渠道年级", grade_rows, ["期次", "渠道展示", "年级", "招生目标", "成单量", "招生进度", "时间进度", "进度GAP", "剩余天数"])}
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
    outputs = []
    for dept in DEPARTMENTS:
        dept_df = df[df["学部"].eq(dept)].copy()
        if dept_df.empty:
            continue
        output = render_department(dept, dept_df)
        if output:
            outputs.append(output)
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
"""


if __name__ == "__main__":
    main()
