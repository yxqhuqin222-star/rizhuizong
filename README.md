# 日追踪看板

读取每日 `tongji_demo.xlsx` 和每周 `tongji_target.xlsx`，生成进度汇总、网页看板和学部播报图，并支持规则化自然语言查询。

![日追踪看板最终实现图](./docs/dashboard-implementation.png)

产品需求和计算口径以 [PRD](./docs/PRD-progress-dashboard.md) 为准，历史变更见 [CHANGELOG](./docs/CHANGELOG.md)。

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
