# 现行业务规则与指标

本文记录当前代码实际执行的口径，便于定位和维护；产品目标及历史背景见 [PRD](./PRD-progress-dashboard.md)，变更时间线见 [CHANGELOG](./CHANGELOG.md)。比例在数据中以小数保存，百分号只用于展示；时间进度为 `0～1`，完成率可能超过 1。下文的 `build_summary.py` 均指 `outputs/tongji_summary/build_summary.py`。

## 输入、粒度与字段

| 项目 | 当前实现 | 代码 |
| --- | --- | --- |
| 输入 | `tongji_demo.xlsx` 的 `rizhuizong_city (17)`；`tongji_target.xlsx` 的 `Sheet1`。缺必要列即报错。 | `outputs/tongji_summary/build_summary.py`：`read_inputs`、`validate_columns` |
| Summary 粒度 | `学部 × 期次 × 线索渠道二级分类 × 价体 × 年级`。target 与 demo 按此完整键外连接，单边缺失的目标或现状补 0。 | `build_summary.py`：`DIMENSIONS`、`build_summary` |
| 日期 | `下单日期`：demo 行日期；Summary 明细展示该键最大下单日期。`进度日期`：同学部同期次 demo 最大下单日期，仅用于进度计算。`进量日期`：target 的业务进度起点。`target_time`：target 的目标日。系统今日只用于播报图生成日期和图片刷新判断，不参与 Summary 进度公式。 | `build_summary.py`：`aggregate_current`、`add_progress_dates`、`calculate_progress`；`reports/build_daily_report_images.py`：`render_department` |
| 日期一致性 | 同学部、同期次的非空 `进量日期` 或 `target_time` 如有多个值则停止生成；空值转为缺失，日期合并取最大非空值，进度在任一必要日期缺失时为空。 | `build_summary.py`：`validate_department_term_dates`、`aggregate_target`、`calculate_progress` |
| 价体 | 输入按原始数值参与匹配；输出时除以 100，整数去掉小数位，例如 `990 → 9.9` 元。 | `build_summary.py`：`format_payment_value` |

`目标`、`现状`、`当日现状`、`差距`、落后项数的单位均为“个/单”，输出为整数；`目标` 和 `现状` 在 `build_summary` 中直接转整数，代码没有对负数、非整数目标设置独立业务校验。日期输出为 `YYYY-MM-DD`。`成单量` 是 demo 的必需列，但 Summary 的现状计算使用 `custom_uid` 去重，不能把原始 `成单量` 求和等同于 Summary 现状。

## 核心公式

| 指标 | 公式、边界与单位 | 代码 |
| --- | --- | --- |
| 目标 | 同一完整键 `sum(target.目标)`；缺 target 键为 0。单位：个。 | `build_summary.py`：`aggregate_target`、`build_summary` |
| 现状 | 同一完整键按 `custom_uid` 去重；缺 `custom_uid` 的每条 demo 行单独计 1；不按 target 进量日期过滤。缺 demo 键为 0。单位：单。 | `build_summary.py`：`aggregate_current`、`build_summary` |
| 当日现状 | 完整键再加 `下单日期`，按上述 `custom_uid` 规则去重。单位：单/日；独立输出到 `daily_summary`，不与累计现状相加。 | `build_summary.py`：`aggregate_current_by_order_date`、`write_outputs` |
| 差距 | `现状 - 目标`；可为负。单位：单。 | `build_summary.py`：`build_summary` |
| 完成率 | `现状 / 目标`；目标为 0 时为空，可大于 100%。单位：比例。 | `build_summary.py`：`build_summary` |
| 时间进度（`进度`） | 任一 `进度日期`、`进量日期`、`target_time` 缺失则为空；`进度日期 < 进量日期` 为 0；`进度日期 >= target_time` 为 1；其余为 `min(进量日期至进度日期含首尾、排除周一的天数, 5) / 6`。目标日前最大 `5/6`。单位：比例。 | `build_summary.py`：`business_progress_days`、`calculate_progress` |
| 范围完成率 | `sum(现状) / sum(目标)`；总目标为 0 时为空，不是逐行完成率的平均。 | `build_summary.py`：`metrics_for`；`web/app.js`：`metricsForRows` |
| 平均进度、落后项数 | 平均进度为有效行进度的算术平均；落后项数为 `目标 > 0` 且进度有效、完成率小于进度的行数。没有有效进度则平均值为空。 | `build_summary.py`：`metrics_for` |
| 招生进度、量级 GAP、进度 GAP | 渠道/年级聚合：`招生进度 = sum(现状) / sum(目标)`，目标 0 时为空；`量级GAP = sum(现状) - sum(目标)`；`进度GAP = clamp(时间进度, 0, 1) - clamp(招生进度, 0, 1)`，任一缺失则为空。GAP 单位分别为单、比例。 | `reports/build_daily_report_images.py`：`aggregate_channel`、`aggregate_grade`、`progress_gap`；`web/app.js`：`dailyAggregateRows`、`dailyGradeAggregateRows` |
| 剩余天数 | 进度缺失显示 `--`；否则 `阶段 = round(进度 × 6)`，阶段达到 6 为 0，其余为 `max(6 - 阶段, 1)`。单位：阶段天数，代码未再查询日历。 | `reports/build_daily_report_images.py`：`remaining_days`；`web/app.js`：`remainingDays` |

**示例（演示值，非当前源表记录）**：某键目标 10、去重现状 4，则差距 `4 - 10 = -6` 单，完成率 `4 / 10 = 40%`。同学部同期次进量日期为 2026-10-06（周二）、进度日期为 2026-10-08（周四）、目标日为 2026-10-12：含首尾计 3 个非周一日，时间进度 `3 / 6 = 50%`，进度 GAP `50% - 40% = +10` 个百分点，状态为“落后”。若进度日期到达目标日，进度直接为 100%。

**精度**：计算用原始数值，不先按展示位数取整；网页百分比显示 1 位小数，工作簿比例单元格格式为 `0.0%`，常规播报图百分比多为整数、总进度播报完成率为 1 位小数。播报图计算 GAP 前将两个比例各自限制在 `0～1`，因此超额完成时显示 GAP 与原始差额可能不同。`web/app.js`：`fmtPercent`；`outputs/tongji_summary/build_workbook.mjs`：数值格式；`reports/build_daily_report_images.py`：`pct_text`、`percent_text`、`progress_gap`。

## 归属、范围和状态

- 渠道以 `外部微转-` 开头时归为 `外部微转-*`。demo 完整键未命中 target，但同学部同期次有 target 时归为 `未报量`，仍保留原价体和年级；完全 demo-only 的期次保留在完整 Summary。代码：`build_summary.py` 的 `normalize_channel`、`assign_unmatched_current_channels`、`assign_unmatched_daily_current_channels`。
- 最新期次以 target 为准，各学部分别按 `春 < 暑 < 秋 < 寒`、期次中的数字排序；并列最高排序键会保留多个期次。默认 `latest_summary` 不含 demo-only 期次；`detail_latest_summary` 还纳入自拼的最新 demo-only 期次。代码：`build_summary.py` 的 `term_key`、`latest_term_rows`、`detail_latest_term_rows`。
- 状态按顺序判断：目标正且现状 0 → `未开单`；目标 0 且现状正 → `仅现状`；目标正、进度有效且完成率低于进度 → `落后`；目标正且完成率至少 1 → `已完成`；完成率比进度至少高 0.1 → `快`；否则 `正常`。状态是展示端判断，Summary payload 不存状态列。代码：`web/app.js` 的 `rowStatus`；`reports/build_daily_report_images.py` 的 `status_text`。
- 累计明细的 `下单日期` 是该键最大日期。点击“展示日数据”或在日期控件选中日期会读取 `daily_summary` / `latest_daily_summary`，展示按日去重的 `当日现状`。渠道、年级与日数据三个按钮可组合：未选日数据时，渠道/年级聚合对累计 Summary 行分组；选中日数据时，按学部、期次、所选渠道/年级维度及下单日期汇总每日 Summary 的 `当日现状`。日数据视图只显示当日进量，不显示日粒度目标、差距、完成率或状态；当前视图 CSV 使用相同的列与行。代码：`build_summary.py` 的 `write_outputs`；`web/app.js` 的 `activeRows`、`aggregateDailyRows`、`renderDailySummary`、`currentExportColumns`。
- 规则化自然语言查询按原始 demo/target 行筛选：当前查询 `成单量` 时求原始列之和，查询 `目标` 时求原始目标之和；成单量问题缺日期、缺业务过滤条件或匹配多义值时要求澄清。业务上已确认查询“成单量”与 Summary“现状”为同一指标，但当前查询未复用 Summary 的 `custom_uid` 去重结果，数值尚不能保证一致。代码：`app.py` 的 `parse_query`、`run_natural_query`、`config/channel_aliases.csv`。
- LEC 专项图固定筛选小学、`LEC内测`、目标表该范围最新期次和原始价体 100/900/990。配置渠道按 `last_from` 与价体计数，`外部微转`按原始渠道前缀计数，剩余量列为`未配置`；实际占比的分母来自同范围 Summary 现状，目标占比由代码内固定报量除以固定报量合计。分母为 0 时占比为 0。代码：`reports/build_daily_report_images.py` 的 `LEC1_CHANNELS`、`filter_lec1_data`、`render_lec1_share`。

## 已确认口径与现存差异

- 日数据视图只显示当日现状及汇总，不增加日粒度差距、完成率或状态；[PRD 第 3.2 节](./PRD-progress-dashboard.md#第-32-节-summary-计算模块)已按此口径修正。
- 自然语言查询“成单量”与 Summary“现状”属于同一业务指标。当前查询求原始 `成单量` 列之和，Summary 按 `custom_uid` 去重；计算路径仍有差异。本次仅记录确认口径，不修改查询结果。
- 最新期次以 `build_summary.py` 的季节优先、数字其次排序为准；`build_workbook.mjs` 的规则文字已修正。现有生成工作簿的规则页须在后续安全重建时同步更新。
