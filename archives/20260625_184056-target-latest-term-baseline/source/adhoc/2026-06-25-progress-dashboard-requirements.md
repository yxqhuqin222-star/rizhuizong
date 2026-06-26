# Source — Progress Dashboard Requirements

Date: 2026-06-25
Kind: adhoc product requirements

## Verbatim / Raw Notes

- Build a web dashboard from the current `summary` table.
- Main usage: check current status and progress every day, with basic statistics and query.
- Every morning the user uploads a new `tongji_demo.xlsx`; `tongji_target.xlsx` is updated weekly.
- The page is only for display and local workflow support.
- Support upload of demo and target files.
- Support export.
- Add a natural-language query entry, but it is low-frequency. Keep it as a small entry aligned under `导出查询明细`, not a large persistent panel.
- Default display should focus on the latest term for each department. Historical terms can be viewed through filters.
- Summary dimensions use renamed Chinese fields:
  - `下单日期`
  - `成单量`
  - `年级`
  - `学部`
  - `期次`
  - `坐席姓名`
  - `部`
  - `团`
  - `组`
  - `价体`
- Summary table display fields:
  - `学部`
  - `期次`
  - `线索渠道二级分类`
  - `价体`
  - `年级`
  - `target_time`
  - `目标`
  - `现状`
  - `差距`
  - `完成率`
  - `进度`
  - status
- `下单日期` is used for progress calculation but should not be shown in the main table.
- Channel rule: values starting with `外部微转-` are summarized as `外部微转-*`.
- Progress formula:
  - `进度 = (总天数 - (target_time - 下单日期)) / 总天数`
  - `总天数 = 6`
  - `下单日期` is the latest date under each summary item.
  - If calculated progress is negative, display it as `100%`.
- Natural-language query v1 should answer examples like:
  - `6月23日，out_wxst_wxstqt_1774944753086 的成单量是多少？`
  - It maps date to `下单日期`, token to `last_from`, and metric to `sum(成单量)`.

