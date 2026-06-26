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
summarySheet.getRangeByIndexes(2, 3, summaryRows, 1).setNumberFormat("#,##0");
summarySheet.getRangeByIndexes(2, 5, summaryRows, 2).setNumberFormat("yyyy-mm-dd");
summarySheet.getRangeByIndexes(2, 7, summaryRows, 3).setNumberFormat("#,##0");
summarySheet.getRangeByIndexes(2, 10, summaryRows, 2).setNumberFormat("0.0%");

const overviewSheet = workbook.worksheets.add("数据概览");
overviewSheet.showGridLines = false;
writeTable(overviewSheet, "基础校验", payload.metadata);
let offset = payload.metadata.rows.length + 4;
for (const [name, table] of Object.entries(payload.distributions)) {
  const label = `维度分布 - ${name}`;
  const height = writeTable(overviewSheet, label, table, offset, 0);
  offset += height + 2;
}

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
