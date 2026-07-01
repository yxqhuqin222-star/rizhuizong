# PRD — Progress Dashboard

## 1. Summary

This is the canonical product specification and calculation reference for the local daily progress dashboard. The dashboard reads daily `demo` data and weekly `target` data, shows the latest-term progress by default, and exports summaries and broadcast images.

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

The original Excel workflow has been implemented as a local web dashboard so daily monitoring is faster and less manual.

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

#### Reload and refresh

- `上传今日 demo` reloads the fixed project-root `tongji_demo.xlsx`.
- `更新 target` reloads the fixed project-root `tongji_target.xlsx`.
- Validate required fields.
- Regenerate Summary and all broadcast images before reporting success.
- Display the actual saved-file update time.
- If the managed local service restarts during an update, retry the request once.

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
- `下单日期 = max(下单日期)` within each item, only as current-status date reference
- `进量日期 = max(进量日期)` from target within each item
- `进度 = (当前日期 - 进量日期 - 1) / 6`
- Progress is clamped to `0%` through `100%`.

Rules:

- `线索渠道二级分类` values beginning with `外部微转-` are grouped as `外部微转-*`.
- `进量日期` is used for progress calculation.
- Status priority is `未开单` / `落后` / `已完成` / `仅现状`, then `快` when `完成率 - 进度 >= 10` percentage points; remaining rows are `正常`.

#### Default latest-term view

- For each `学部`, identify the latest `期次` from the `target` table.
- If a `demo` row belongs to a newer term that does not exist in the `target` table, keep it in full Summary but exclude it from the default latest-term view.
- Default table and KPI cards use only those rows.
- The overview shows separate primary, middle, and high school rows; it does not show aggregate or self-study rows.
- The detail view defaults to the `快` quick filter.
- Clicking a department's lagging-item count opens the latest-term detail filtered to that department and rows whose completion rate is below progress.
- The user can select all terms or a specific term through filters.

#### Export

- Export latest-term summary.
- Export full summary.
- Export query results.
- Export daily progress broadcast images for `小学`, `初中`, and `高中`.
- Broadcast daily progress images for `小学`, `初中`, and `高中` to the DingTalk group robot.
- Image downloads open in a new browser tab and leave the dashboard open.

Daily progress broadcast field mapping:

- Scope: only each department's latest `期次` from the `target` table; historical terms and demo-only newer terms are not shown in broadcast images.
- `渠道展示 = 线索渠道二级分类 + 价体`
- `招生目标 = 目标`
- `进度GAP = 时间进度 - 招生进度`，两个进度均按页面展示口径限制在 `0%–100%`，并保留正负号。
- `剩余天数 = 总天数 - (target_time - 进量日期 - 1)`
- `状态` uses the same classification as the dashboard.
- Grade rows use business order: 小学二至六年级、初中初一至初三、高中高一至高三。

DingTalk broadcast note:

- The custom robot sends a markdown image message with the required keyword `成单`.
- For group members to render the image reliably, the image URL should be reachable from DingTalk clients. Configure `DINGTALK_REPORT_BASE_URL` when the local service is exposed through an accessible host.

#### Natural-language query V1

Supported query behavior:

- Date + channel alias, `last_from`, or shared business dimensions + `成单量` / `进量` / `目标`.
- Channel aliases are resolved through `config/channel_aliases.csv`.
- Relative dates such as `昨天` resolve from the current date.
- `LLM9.9` resolves to `线索渠道二级分类 = LLM外呼` and `价体 = 990`.
- Query vocabulary is built from values in both `demo` and `target`.
- Shared dimensions can be combined; `成单量` comes from `demo`, while `目标` comes from `target`.
- `小初高各学部` and `三个学部分别` return per-department results and a combined total.
- If the metric is omitted, use `成单量` without asking for confirmation.
- When a required condition is missing, the page asks for one missing condition at a time instead of guessing.
- Clarification is limited to two rounds and is stored only in the current page session.

Example:

- `6月23日，out_wxst_wxstqt_1774944753086 的成单量是多少？`
- `YZY渠道的进量` → asks `你想查询哪个时间段的？` → `6月27日`.

Output:

- Sum of `成单量`.
- Matched row count.
- Paginated matching rows, defaulting to 10 rows per page with 10 / 20 / 50 options.
- Exportable full matching rows.
- The original query, clarification questions, and answers stay visible until completion or restart.

### 7.3 Technology

The current implementation uses:

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
- Natural-language query remains rule-based and does not use an external model.
- Missing conditions are never inferred from defaults; the user must confirm them.

## 8. Release

### V1

- Local dashboard, managed restart, and health check.
- Reload fixed demo/target files.
- Regenerate summary.
- Default latest-term view.
- Filters and KPI cards.
- Export latest/full/query data.
- Rule-based natural-language query with at most two clarification rounds.
- Separate department broadcast images and DingTalk robot delivery.

### Verification

- Summary totals and calculation fields match the final generated workbook.
- Latest-term metrics use only the latest target term for each department.
- Query examples return the expected total, matched-row count, and export rows.
- Latest/full/query downloads return valid files.
- Broadcast image downloads return valid PNG files generated from the latest Summary.
- The running service returns a healthy response from `/api/health`.

### V2

- Richer natural-language analysis.
- Trend charts.
- Historical upload records.
- Editable targets in the page.
- User accounts or deployment, if needed.
