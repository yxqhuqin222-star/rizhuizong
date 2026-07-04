import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outDir = "/Users/kityhello/workplace/project/rizhuizong/outputs/tongji_summary";
const payload = JSON.parse(await fs.readFile(`${outDir}/summary_payload.json`, "utf8"));

function writeTable(sheet, title, table, startRow = 0, startCol = 0) {
  const rowCount = table.rows.length + 2;
  const colCount = table.headers.length;
  sheet.getRangeByIndexes(startRow, startCol, 1, colCount).merge();
  const titleRange = sheet.getRangeByIndexes(startRow, startCol, 1, colCount);
  titleRange.values = [[title]];
  titleRange.format.fill.color = "#17365D";
  titleRange.format.font.color = "#FFFFFF";
  titleRange.format.font.bold = true;
  titleRange.format.font.size = 14;

  const headerRange = sheet.getRangeByIndexes(startRow + 1, startCol, 1, colCount);
  headerRange.values = [table.headers];
  headerRange.format.fill.color = "#D9EAF7";
  headerRange.format.font.bold = true;
  headerRange.format.borders = { preset: "doubleBottom", style: "thin", color: "#7F9DB9" };

  if (table.rows.length > 0) {
    const bodyRange = sheet.getRangeByIndexes(startRow + 2, startCol, table.rows.length, colCount);
    bodyRange.values = table.rows;
    bodyRange.format.borders = { preset: "inside", style: "thin", color: "#E6EEF5" };
  }

  const fullRange = sheet.getRangeByIndexes(startRow, startCol, rowCount, colCount);
  fullRange.format.autofitColumns();
  fullRange.format.autofitRows();
  return rowCount;
}

const workbook = Workbook.create();

const summarySheet = workbook.worksheets.add("目标现状对比");
summarySheet.showGridLines = false;
writeTable(summarySheet, "目标 + 现状对比", payload.summary);
summarySheet.freezePanes.freezeRows(2);
const summaryRows = payload.summary.rows.length;
summarySheet.getRangeByIndexes(2, 3, summaryRows, 1).setNumberFormat("0.##");
summarySheet.getRangeByIndexes(2, 5, summaryRows, 3).setNumberFormat("yyyy-mm-dd");
summarySheet.getRangeByIndexes(2, 8, summaryRows, 3).setNumberFormat("#,##0");
summarySheet.getRangeByIndexes(2, 11, summaryRows, 2).setNumberFormat("0.0%");

const overviewSheet = workbook.worksheets.add("数据概览");
overviewSheet.showGridLines = false;
writeTable(overviewSheet, "基础校验", payload.metadata);
let offset = payload.metadata.rows.length + 4;
for (const [name, table] of Object.entries(payload.distributions)) {
  const label = `维度分布 - ${name}`;
  const height = writeTable(overviewSheet, label, table, offset, 0);
  offset += height + 2;
}

const rulesSheet = workbook.worksheets.add("计算规则");
rulesSheet.showGridLines = false;
const calculationRules = {
  headers: ["分类", "项目", "计算规则"],
  rows: [
    ["聚合范围", "统计维度", "按学部、期次、线索渠道二级分类、价体、年级聚合"],
    ["展示格式", "价体", "原始价体除以 100，去除无意义的小数位，例如 100→1、990→9.9、1880→18.8"],
    ["字段归并", "线索渠道二级分类", "以“外部微转-”开头的值统一归为“外部微转-*”"],
    ["字段归并", "未命中 target 的渠道", "常规外呼未命中 target 时保留为仅现状项；其他渠道按同一学部、期次、价体、年级寻找 target 渠道，唯一候选直接归属，多个候选优先常规外呼、其次 LEC内测，两者都没有时报错，无候选保留为仅现状项"],
    ["目标", "目标", "同一统计维度下 target 表的目标之和"],
    ["目标", "target_time", "同一统计维度下 target 表的最晚 target_time"],
    ["目标", "进量日期", "同一统计维度下 target 表的最晚进量日期"],
    ["现状", "现状", "同一统计维度下按 custom_uid 去重计数；custom_uid 缺失的行分别计数"],
    ["现状", "下单日期", "同一统计维度下 demo 表的最近一次下单日期，用于明细展示"],
    ["对比指标", "差距", "现状 - 目标"],
    ["对比指标", "完成率", "现状 ÷ 目标；目标为 0 时留空"],
    ["对比指标", "进度", "（当前日期 - 进量日期 + 1）÷ 总天数；当前日期统一取同学部、同一期次 demo 的最近下单日期；总天数为 6 天，结果限制在 0%～100%"],
    ["校验", "日期一致性", "同学部、同一期次的 target_time 和进量日期必须分别唯一，否则停止生成"],
    ["合并规则", "目标与现状", "按统计维度全量合并；仅有目标或仅有现状的组合也保留，缺失的目标/现状按 0 计算"],
    ["最新期次", "默认范围", "以 target 表中的期次为准，每个学部取数字序号最大的期次"],
    ["最新期次", "demo-only 期次", "保留在完整 Summary 中，但不进入默认最新期次范围"],
    ["整体指标", "完成率整体", "现状合计 ÷ 目标合计；目标合计为 0 时留空"],
    ["整体指标", "平均进度", "所选范围内有有效进度值的各统计项进度算术平均"],
    ["整体指标", "落后项", "完成率低于进度，且进度值有效的统计项数量"],
  ],
};
writeTable(rulesSheet, "Summary 计算规则", calculationRules);
rulesSheet.freezePanes.freezeRows(2);
rulesSheet.getRange("A1:C21").format.wrapText = true;
rulesSheet.getRange("A1:A21").format.columnWidth = 14;
rulesSheet.getRange("B1:B21").format.columnWidth = 18;
rulesSheet.getRange("C1:C21").format.columnWidth = 72;
rulesSheet.getRange("A1:C21").format.autofitRows();

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "formula error scan",
});
console.log(errors.ndjson);

const preview = await workbook.render({
  sheetName: "目标现状对比",
  range: "A1:L25",
  scale: 1,
  format: "png",
});
await fs.writeFile(`${outDir}/tongji_summary_preview.png`, new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outDir}/tongji_summary_current.xlsx`);
console.log(`${outDir}/tongji_summary_current.xlsx`);
