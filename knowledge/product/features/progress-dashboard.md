# Feature — Progress Dashboard

## Meta
- Owner: User
- Status: building
- Priority: high
- Last updated: 2026-06-27

## Problem

The user needs to check daily progress against targets quickly after uploading a new `demo` file. The current Excel-based workflow works, but it requires manual file handling and does not provide a focused latest-term dashboard.

## Target users

- Internal operator or business owner who monitors daily progress.

## Success metrics

- Daily `demo` upload produces refreshed summary data.
- Clicking `上传今日 demo` directly reloads the fixed project-root `tongji_demo.xlsx` without opening a file picker.
- Default view shows latest-term data only.
- Latest-term overview shows separate primary, middle, and high school metric rows without an aggregate or self-study row.
- Clicking a department's lagging-item count opens the existing latest-term detail view filtered to that department and rows whose completion rate is below progress; unopened rows remain labeled `未开单`.
- User can export latest-term and full summary data.
- User can export separate daily progress broadcast images for primary, middle, and high school views.
- User can send primary, middle, and high school daily progress broadcast images to the configured DingTalk group robot.
- Date + `last_from` query returns the correct `成单量`.

## Daily Broadcast Field Mapping

- Scope: only each department's latest `期次` from the `target` table; historical terms and demo-only newer terms are not shown in broadcast images.
- `渠道展示 = 线索渠道二级分类 + 价体`
- `招生目标 = 目标`
- `剩余天数 = 总天数 - (target_time - 进量日期)`
- `状态` matches the dashboard status rule: 未开单 / 落后 / 已完成 / 仅现状 / 快 / 正常. `快` means `完成率 - 进度 >= 10` percentage points after higher-priority statuses are excluded.
- Dashboard and broadcast grade rows follow business order: 小学二至六年级、初中初一至初三、高中高一至高三.

## Risks

- Excel field names may drift.
- Latest-term detection may need adjustment if `target` table `期次` naming changes.
- Natural-language query may be expected to support more patterns than V1.

## Dependencies

- `tongji_demo.xlsx`
- `tongji_target.xlsx`
- `outputs/tongji_summary/build_summary.py`
- DingTalk custom robot webhook for group broadcast.

## Timeline

- Now: V1 local web app build.
- Next: User review and polish.
- Later: V2 charts/history/advanced query.

## Evidence

- Requirements source: [source/adhoc/2026-06-25-progress-dashboard-requirements.md](../../../source/adhoc/2026-06-25-progress-dashboard-requirements.md)
- Prototype: [design-demos/summary_dashboard_v1.html](../../../design-demos/summary_dashboard_v1.html)

## Linked

- PRD: [docs/PRD-progress-dashboard.md](../../../docs/PRD-progress-dashboard.md)
- Decision: [decisions/2026-06-25-local-file-dashboard.md](../../../decisions/2026-06-25-local-file-dashboard.md)

## Open questions

- Should `target_time` eventually be renamed to Chinese in the source Excel?
- Should V2 store daily upload history?
- Should the local dashboard be exposed through a stable internal/public URL so DingTalk markdown images render for every group member?

## Follow-up after launch

- Verify the dashboard after at least one real daily `demo` upload.
- Track which filters and exports are used most often.
