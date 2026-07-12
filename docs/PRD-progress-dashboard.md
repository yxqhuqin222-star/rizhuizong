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
- [design-demos/live_dashboard_with_dingtalk.png](../design-demos/live_dashboard_with_dingtalk.png)

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
- Record and display the successful upload/reload time for each document.
- File modification, page refresh, summary regeneration, and service restart must not change the displayed upload time.
- Before the first successful upload/reload record exists, display `尚未上传`.
- If the managed local service restarts during an update, retry the request once.
- After a local reload succeeds, sync the latest state, workbook, and broadcast images to the production read-only site.
- If online sync fails, keep the local reload result and show the sync failure in the update status.

#### Summary calculation

Dimensions:

- `学部`
- `期次`
- `线索渠道二级分类`
- `价体`
- `年级`

Measures:

- `目标 = sum(目标)`
- `现状 = count(distinct custom_uid)` within each complete statistical dimension after excluding demo rows whose `下单日期` is earlier than the same `学部` and `期次` target `进量日期`; rows without `custom_uid` are counted separately.
- `差距 = 现状 - 目标`
- `完成率 = 现状 / 目标`
- `下单日期 = max(下单日期)` within each item, for detail display
- `进量日期 = max(进量日期)` from target within each item
- `当前日期 = max(下单日期)` from demo within the same `学部` and `期次`；三个学部可使用各自不同的最新下单日期。
- If `当前日期 < 进量日期`, `进度 = 0`; if `进量日期 <= 当前日期 < target_time`, `进度 = min(当前日期 - 进量日期 + 1, 5) / 6`; if `当前日期 >= target_time`, `进度 = 100%`.
- Progress is clamped to `0%` through `100%`.

Rules:

- `线索渠道二级分类` values beginning with `外部微转-` are grouped as `外部微转-*`.
- demo 中的 `常规外呼` 按完整统计维度无法命中 target 时保留为仅现状项，不改归其他渠道。其他渠道无法命中时，改用同一 `学部`、`期次`、`价体`、`年级`寻找 target 渠道；只有一个候选时归入唯一候选，多个候选时优先归入 `常规外呼`，没有 `常规外呼` 时归入 `LEC内测`，两个优先渠道都不存在时停止生成并报错，没有候选时保留为仅现状项。
- When a `demo` row belongs to a `学部` and `期次` that has a target `进量日期`, count it only if `下单日期 >= 进量日期`. `demo` rows without a matching department-term target intake date are kept as current-only rows.
- 原始文件中的 `价体` 保持不变；看板、查询结果和导出文件统一显示为原始值除以 100，并去除无意义的小数位，例如 `0→0`、`100→1`、`990→9.9`、`1880→18.8`、`2880→28.8`。
- All rows in the same `学部` and `期次` use the same current date for progress calculation, regardless of channel, price, or grade.
- Within one `学部` and `期次`, `target_time` and `进量日期` must each be unique; generation stops with an error if either field has conflicting values.
- Rows without a department-term current date, `target_time`, or `进量日期` have no progress value.
- Status priority is `未开单` / `仅现状` / `落后` / `已完成`, then `快` when `完成率 - 进度 >= 10` percentage points; remaining rows are `正常`. Only rows with `目标 > 0` can be classified as `落后`. Rows with `目标 = 0` and `现状 > 0` are `仅现状`; rows with `目标 = 0` are not included in the behind count.

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
- `渠道展示 = 线索渠道二级分类 + 格式化后的价体`
- `招生目标 = 目标`
- `进度GAP = 时间进度 - 招生进度`，两个进度均按页面展示口径限制在 `0%–100%`，并保留正负号。
- 每期按 6 个业务日折算，每周一为业务休息日；`剩余天数 = max(6 - 当前进度阶段, 1)`，其中 `当前进度阶段 = 进度 × 6`。剩余天数与进度使用同一计算结果，不再按自然日期相减。
- `状态` uses the same classification as the dashboard.
- Grade rows use business order: 小学二至六年级、初中初一至初三、高中高一至高三。
- `lec1元占比` 固定统计小学 `暑_10`、`LEC内测`、1 元数据，过滤、渠道归属和去重口径与进度表 `现状` 一致：按学部期次进量日期过滤，未命中 target 的渠道按 Summary 规则归属，同一统计范围内按 `custom_uid` 去重。渠道顺序与目标占比为：YZY 25%、WC 15%、RQ 20%、JJ 8%、SH 12%、ZXC 5%、微转 12%、HFS 3%、YD 0%、爆量本地化 0%；没有目标的渠道目标占比显示 0%，实际占比按各展示渠道成单量除以全部展示渠道成单量计算。渠道按完整 `last_from` 精确匹配，表中仅展示末三位。

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
- 字段值匹配忽略英文大小写、空格、下划线和连字符；例如 `lec内测`、`L-E_C 内测` 均匹配实际字段值 `LEC内测`。存在多个匹配值时必须要求用户确认，不能静默选择。
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
- Production `/api/state` and `/download/workbook` can serve the latest synced cloud copy, with static build output as fallback.

### V2

- Richer natural-language analysis.
- Trend charts.
- Historical upload records.
- Editable targets in the page.
- User accounts or deployment, if needed.
