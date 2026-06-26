# PRD — Progress Dashboard

## 1. Summary

This document defines V1 of a local progress dashboard for daily sales progress tracking. The dashboard lets the user upload daily `demo` data, reuse or update weekly `target` data, view the latest-term progress table by default, and export the results.

## 2. Contacts

| Name | Role | Comment |
| --- | --- | --- |
| User | Product owner and operator | Uses the dashboard each morning to inspect progress and export data. |
| Codex | Builder | Implements the local web app, data processing, and documentation. |

## 3. Background

The current workflow uses Excel files:

- `tongji_demo.xlsx` changes daily.
- `tongji_target.xlsx` changes weekly.
- A generated `summary` table compares target, current status, gap, completion rate, and progress.

The user has already validated the summary calculation. The next step is to turn the workflow into a simple local web dashboard so daily monitoring is faster and less manual.

## 4. Objective

The objective is to build a local web dashboard that makes latest-term progress easy to inspect after each daily data upload.

### Key Results

- KR1: After uploading a new `demo` file, the dashboard regenerates summary data without manual script edits.
- KR2: The default dashboard view shows only each `学部`'s latest `期次`.
- KR3: The user can switch to all terms through filtering.
- KR4: The user can export latest-term summary, full summary, and query results.
- KR5: A date + `last_from` natural-language query returns `sum(成单量)` with matched row count.

## 5. Market Segment(s)

The first user is an internal operator or business owner who checks daily progress against weekly targets. The job is not broad BI exploration. The job is fast operational monitoring.

Constraints:

- The solution should run locally.
- The data source is Excel.
- V1 should not require login, database setup, or cloud deployment.

## 6. Value Proposition(s)

The dashboard helps the user:

- Avoid rebuilding the same summary manually each morning.
- See the latest active term first.
- Keep historical terms available but out of the default view.
- Export data for follow-up work.
- Ask simple natural-language questions without manually filtering raw Excel rows.

## 7. Solution

### 7.1 UX / Prototype

The current prototype is:

- [design-demos/summary_dashboard_v1.html](../design-demos/summary_dashboard_v1.html)
- [design-demos/summary_dashboard_v1.png](../design-demos/summary_dashboard_v1.png)

V1 layout:

- Left sidebar:
  - Upload daily demo.
  - Update weekly target.
  - Export latest term.
  - Export full summary.
  - Export query details.
  - Natural-language query entry.
- Main content:
  - KPI cards.
  - Latest-term summary table.
  - Filters for `学部`, `期次`, `线索渠道二级分类`, `价体`, and keyword.

### 7.2 Key Features

#### Upload and refresh

- Upload `tongji_demo.xlsx`.
- Upload `tongji_target.xlsx`.
- Validate required fields.
- Regenerate summary.

#### Summary calculation

Dimensions:

- `学部`
- `期次`
- `线索渠道二级分类`
- `价体`
- `年级`

Measures:

- `目标 = sum(目标)`
- `现状 = sum(成单量)`
- `差距 = 现状 - 目标`
- `完成率 = 现状 / 目标`
- `下单日期 = max(下单日期)` within each item
- `进度 = (6 - (target_time - 下单日期)) / 6`
- If progress is negative, show it as `100%`.

Rules:

- `线索渠道二级分类` values beginning with `外部微转-` are grouped as `外部微转-*`.
- `下单日期` is used for calculation but not shown in the main table.

#### Default latest-term view

- For each `学部`, identify the latest `期次` from the `target` table.
- If a `demo` row belongs to a newer term that does not exist in the `target` table, keep it in full Summary but exclude it from the default latest-term view.
- Default table and KPI cards use only those rows.
- The user can select all terms or a specific term through filters.

#### Export

- Export latest-term summary.
- Export full summary.
- Export query results.
- Export daily progress broadcast images for `小学`, `初中`, and `高中`.

Daily progress broadcast field mapping:

- Scope: only each department's latest `期次` from the `target` table; historical terms and demo-only newer terms are not shown in broadcast images.
- `渠道展示 = 线索渠道二级分类 + 价体`
- `招生目标 = 目标`
- `剩余天数 = 总天数 - (target_time - 下单日期)`

#### Natural-language query V1

Supported query:

- Date + `last_from` + `成单量`.

Example:

- `6月23日，out_wxst_wxstqt_1774944753086 的成单量是多少？`

Output:

- Sum of `成单量`.
- Matched row count.
- Exportable matching rows.

### 7.3 Technology

V1 will use:

- Python local HTTP server.
- Pandas for Excel processing.
- Static HTML/CSS/JavaScript frontend.
- File-based storage in the project directory.

No database, login, external API, or cloud service is required for V1.

### 7.4 Assumptions

- The user runs this locally.
- Excel field names stay aligned with the confirmed Chinese names.
- `target_time` remains the target-date field name.
- Latest term is determined from the `target` table by the numeric suffix in `期次`, such as `暑_10 > 暑_9`.
- Natural-language query V1 only needs the date + `last_from` pattern.

## 8. Release

### V1

- Local dashboard.
- Upload demo/target.
- Regenerate summary.
- Default latest-term view.
- Filters and KPI cards.
- Export latest/full/query data.
- Simple natural-language query.

### V2

- Richer natural-language analysis.
- Trend charts.
- Historical upload records.
- Editable targets in the page.
- User accounts or deployment, if needed.
