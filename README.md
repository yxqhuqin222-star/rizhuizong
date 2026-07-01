# 日追踪看板

读取每日 `tongji_demo.xlsx` 和每周 `tongji_target.xlsx`，生成进度汇总、网页看板和学部播报图，并支持规则化自然语言查询。

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
- 健康检查：`GET /api/health`
- 页面入口：`http://127.0.0.1:8766`
- 修改产品行为前先核对 [PRD](./docs/PRD-progress-dashboard.md)。
