# Changelog — 日追踪看板

所有重要功能变更都记录在这里。最新变更放在最上方。

## 2026-06-25

### Added

- 搭建本地网页看板 V1，用于查看 `tongji_demo.xlsx` 和 `tongji_target.xlsx` 生成的进度监控数据。
- 支持上传每日 `demo` 文件、更新每周 `target` 文件，并重新生成 summary。
- 默认展示每个 `学部` 的最新 `期次` 数据，历史期次可通过筛选查看。
- 增加 KPI 卡片：最新期次目标、现状、完成率、平均进度、落后项。
- 增加筛选能力：`学部`、`期次`、`线索渠道二级分类`、`价体`、关键词。
- 增加导出能力：导出最新期次、导出完整 Summary、导出查询明细。
- 增加自然语言查询入口，V1 支持按日期和 `last_from` 查询 `成单量`。
- 增加每日进度播报图导出，分别生成小学、初中、高中三张 PNG 图片。

### Changed

- summary 字段统一为业务中文字段：`学部`、`期次`、`线索渠道二级分类`、`价体`、`年级`、`下单日期`、`成单量`。
- `线索渠道二级分类` 中以 `外部微转-` 开头的分类统一汇总为 `外部微转-*`。
- 主表展示顺序调整为：`学部`、`期次`、`线索渠道二级分类`、`价体`、`年级`、`target_time`、`目标`、`现状`、`差距`、`完成率`、`进度`、`状态`。
- 主表不再展示 `下单日期`，但仍用它计算进度。
- 当进度计算结果为负值时，展示为 `100%`。
- 自然语言查询改为低频入口，放到导出区域底部，不占用主监控区域。
- 明确播报图字段口径：`渠道展示 = 线索渠道二级分类 + 价体`，`招生目标 = 目标`，`剩余天数 = 总天数 - (target_time - 下单日期)`。
- 播报图只展示小学、初中、高中各自最新一期次数据，不展示历史期次。
- summary 工作簿的“数据概览”增加默认展示口径、最新期次范围、最新期次指标和播报图字段口径；维度分布改为围绕最新期次 summary 展示 `目标` 和 `现状`。
- 播报图生成时会强制规范化 summary 中的日期和数值字段，避免新底表导出后出现字符串与空值混合导致生成失败。
- 最新期次口径改为以 `target` 表中的期次为准；demo 中存在但 target 中不存在的更晚期次保留在完整 Summary，不进入默认看板和播报图。

### Verified

- 已验证 summary 接口可返回最新期次指标。
- 已验证自然语言查询示例可返回对应 `成单量`。
- 已验证播报图下载接口可返回有效 PNG。

### Related Files

- PRD: [PRD-progress-dashboard.md](./PRD-progress-dashboard.md)
- Development plan: [development-plan.md](./development-plan.md)
- Feature record: [progress-dashboard.md](../knowledge/product/features/progress-dashboard.md)
- Architecture decision: [2026-06-25-local-file-dashboard.md](../decisions/2026-06-25-local-file-dashboard.md)
