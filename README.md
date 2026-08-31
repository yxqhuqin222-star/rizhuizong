# 日追踪看板

读取每日 `tongji_demo.xlsx` 和每周 `tongji_target.xlsx`，生成统一 Summary、网页看板、工作簿、总进度/学部/专项播报图，并支持线上只读同步、钉钉群播报和规则化自然语言查询。

![日追踪看板最终实现图](./docs/dashboard-implementation.png)

产品需求、计算口径和钉钉播报链路以 [PRD](./docs/PRD-progress-dashboard.md) 为准，历史变更见 [CHANGELOG](./docs/CHANGELOG.md)。

## 当前能力

- 默认按 target 表确定小学、初中、高中、自拼各自最新期次，概览、明细、工作簿、播报图和线上只读 state 共用同一份 Summary。
- 明细支持最新期次/全部期次切换、多选筛选、当前视图 CSV 导出，以及「展示日数据」「渠道聚合」「年级聚合」三种日数据查看方式。
- 支持总进度、小学、初中、高中、自拼、`lec1元占比` 六类播报图下载；本地配置钉钉 webhook 后可发送到群。
- 本地更新 demo 或 target 后会重算 Summary、工作簿和播报图，并把 state、工作簿和播报图同步到线上只读看板；失败时进入本地补偿队列。
- 自然语言查询支持日期、渠道别名、last_from、学部、期次、价体、年级等组合条件，并可导出查询明细。

## 当前图片样例

| 图片 | 路径 | 用途 |
|---|---|---|
| 看板截图 | [docs/dashboard-implementation.png](./docs/dashboard-implementation.png) | README 首页预览，展示当前年级聚合视图 |
| 技术路线图 | [docs/project-technical-roadmap.png](./docs/project-technical-roadmap.png) | 说明 Excel -> Summary -> 工作簿/播报图/线上只读链路 |
| 总进度播报图 | [reports/daily_progress/overall_progress.png](./reports/daily_progress/overall_progress.png) | 各学部最新期次总览 |
| 小学播报图 | [reports/daily_progress/primary_daily_progress.png](./reports/daily_progress/primary_daily_progress.png) | 小学最新期次进度播报 |
| 初中播报图 | [reports/daily_progress/middle_daily_progress.png](./reports/daily_progress/middle_daily_progress.png) | 初中最新期次进度播报 |
| 高中播报图 | [reports/daily_progress/high_daily_progress.png](./reports/daily_progress/high_daily_progress.png) | 高中最新期次进度播报 |
| 自拼播报图 | [reports/daily_progress/zipin_daily_progress.png](./reports/daily_progress/zipin_daily_progress.png) | 自拼最新期次进度播报 |
| 1 元占比播报图 | [reports/daily_progress/lec1_share.png](./reports/daily_progress/lec1_share.png) | LEC 内测小学量级专项播报 |

## 目录

```
app.py               本地 HTTP 服务和 API
web/                 看板前端
outputs/             Summary 计算、工作簿和中间结果
reports/             播报图生成与导出
config/              渠道别名和本地服务配置
tests/               自动化测试
docs/                PRD 和变更记录
decisions/           架构决策
source/              原始需求证据
rules/               项目规则
archives/            历史压缩快照
```

## 常用操作

- 启动与重启：`scripts/restart_dashboard.sh`
- 发布只读看板：`python3 scripts/publish_netlify.py`
- 线上只读看板：`https://kityhello.dpdns.org/web/index.html`
- 健康检查：`GET /api/health`
- 页面入口：`http://127.0.0.1:8766`
- 修改产品行为前先核对 [PRD](./docs/PRD-progress-dashboard.md)。

## 线上实时同步

本地点击 `上传今日 demo` 或 `更新 target` 后，会先重算本地 Summary、工作簿和播报图，再把最新状态同步到线上只读看板。同步成功后，线上页面刷新即可看到最新数据；同步失败时，本地更新仍保留，页面会显示失败原因。

本地同步复用 `.env.local` 中的 `REPORT_UPLOAD_TOKEN`，也可以单独配置 `DASHBOARD_SYNC_TOKEN`。默认同步地址是 `https://kityhello.dpdns.org/api/state` 和 `https://kityhello.dpdns.org/download/workbook`。

## 钉钉播报

看板支持生成总进度、小学、初中、高中、自拼每日招生进度播报图，以及 `lec1元占比` 播报图。用户可以在本地看板下载图片，也可以通过钉钉机器人发送到群里。

播报图样例和字段口径见 [PRD 的播报图与钉钉模块](./docs/PRD-progress-dashboard.md#第-35-节-播报图与钉钉模块)。真实群播报需要配置 `DINGTALK_WEBHOOK`；如果钉钉客户端需要访问公网图片地址，还需要配置 `DINGTALK_REPORT_BASE_URL`，或配合 `REPORT_IMAGE_UPLOAD_URL` 和 `REPORT_UPLOAD_TOKEN` 上传图片。
