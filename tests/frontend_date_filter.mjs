import { chromium } from "playwright";
import { readFile } from "node:fs/promises";

const baseUrl = process.argv[2];
const executablePath = process.env.PLAYWRIGHT_CHROME_EXECUTABLE
  || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const summaryRow = {
  "学部": "小学",
  "期次": "秋_5",
  "线索渠道二级分类": "LEC内测",
  "价体": 1,
  "年级": "三年级",
  "下单日期": "2026-10-07",
  "target_time": "2026-10-14",
  "进量日期": "2026-10-04",
  "目标": 100,
  "现状": 12,
  "当日现状": 7,
  "差距": -88,
  "完成率": 0.12,
  "进度": 0.5,
};

const dailyRows = [
  {
    "学部": "小学",
    "期次": "秋_5",
    "线索渠道二级分类": "LEC内测",
    "价体": 1,
    "年级": "三年级",
    "下单日期": "2026-10-06",
    "当日现状": 5,
  },
  {
    "学部": "小学",
    "期次": "秋_5",
    "线索渠道二级分类": "LEC内测",
    "价体": 1,
    "年级": "三年级",
    "下单日期": "2026-10-07",
    "当日现状": 7,
  },
  ...[
    ["小学", "一年级", "2026-10-08"],
    ["小学", "一年级", "2026-10-07"],
    ["小学", "六年级", "2026-10-08"],
    ["小学", "六年级", "2026-10-07"],
    ["初中", "初三", "2026-10-07"],
    ["初中", "初三", "2026-10-08"],
    ["初中", "初一", "2026-10-07"],
    ["初中", "初一", "2026-10-08"],
    ["初中", "初二", "2026-10-07"],
    ["初中", "初二", "2026-10-08"],
    ["高中", "高三", "2026-10-07"],
    ["高中", "高三", "2026-10-08"],
    ["高中", "高一", "2026-10-07"],
    ["高中", "高一", "2026-10-08"],
    ["高中", "高二", "2026-10-07"],
    ["高中", "高二", "2026-10-08"],
  ].map(([department, grade, orderDate]) => ({
    "学部": department,
    "期次": "秋_5",
    "线索渠道二级分类": "测试渠道",
    "价体": 1,
    "年级": grade,
    "下单日期": orderDate,
    "当日现状": 1,
  })),
];

const state = {
  summary: [summaryRow],
  latestSummary: [summaryRow],
  detailLatestSummary: [summaryRow],
  dailySummary: dailyRows,
  latestDailySummary: dailyRows,
  metrics: {
    latest: {
      target_total: 100,
      current_total: 12,
      completion: 0.12,
      avg_progress: 0.5,
      behind_count: 1,
    },
  },
  files: { demo: null, target: null },
  reportUrls: {},
  sync: {},
};

const browser = await chromium.launch({ headless: true, executablePath });
const page = await browser.newPage({ locale: "zh-CN" });

try {
  await page.route("**/api/state", route => route.fulfill({ json: state }));
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => document.querySelectorAll("#summaryBody tr").length === 1);

  await page.click("#toggleDailyButton");
  await page.waitForFunction(expected => document.querySelectorAll("#summaryBody tr").length === expected, dailyRows.length);
  const sortedRows = await page.evaluate(() => [...document.querySelectorAll("#summaryBody tr")].map(row => {
    const cells = row.querySelectorAll("td");
    return [cells[0]?.textContent, cells[4]?.textContent, cells[5]?.textContent];
  }));
  for (const [department, expected] of [
    ["小学", [["一年级", "2026-10-08"], ["一年级", "2026-10-07"], ["六年级", "2026-10-08"], ["六年级", "2026-10-07"]]],
    ["初中", [["初一", "2026-10-08"], ["初一", "2026-10-07"], ["初二", "2026-10-08"], ["初二", "2026-10-07"], ["初三", "2026-10-08"], ["初三", "2026-10-07"]]],
    ["高中", [["高一", "2026-10-08"], ["高一", "2026-10-07"], ["高二", "2026-10-08"], ["高二", "2026-10-07"], ["高三", "2026-10-08"], ["高三", "2026-10-07"]]],
  ]) {
    const actual = sortedRows.filter(row => row[0] === department && row[1] !== "三年级").map(row => row.slice(1));
    if (JSON.stringify(actual) !== JSON.stringify(expected)) {
      throw new Error(`${department} grade/date order is wrong: ${JSON.stringify(actual)}`);
    }
  }

  for (const [container, value] of [
    ["filterDepartment", "小学"],
    ["filterOrderDate", "2026-10-06"],
  ]) {
    await page.evaluate(({ container, value }) => {
      const input = document.querySelector(`#${container} input[value="${value}"]`);
      if (!input) throw new Error(`missing filter ${container}=${value}`);
      input.checked = true;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }, { container, value });
  }

  const result = await page.evaluate(() => ({
    title: document.querySelector("#tableTitle")?.textContent,
    summary: document.querySelector("#filteredSummary")?.innerText,
    rowCount: document.querySelectorAll("#summaryBody tr").length,
    dailyPressed: document.querySelector("#toggleDailyButton")?.getAttribute("aria-pressed"),
  }));

  if (!result.title?.includes("日数据")) {
    throw new Error(`date filter did not activate daily data: ${JSON.stringify(result)}`);
  }
  if (!result.summary?.includes("当日进量") || !result.summary?.includes("5")) {
    throw new Error(`daily total is missing: ${JSON.stringify(result)}`);
  }
  if (result.rowCount !== 1 || result.dailyPressed !== "true") {
    throw new Error(`daily row was not rendered: ${JSON.stringify(result)}`);
  }

  await page.click("#dailyChannelAggregateButton");
  const channelDate = await page.evaluate(() => ({
    title: document.querySelector("#tableTitle")?.textContent,
    headers: [...document.querySelectorAll("#summaryHead th")].map(cell => cell.textContent),
    row: [...document.querySelectorAll("#summaryBody tr")].map(tr => [...tr.querySelectorAll("td")].map(td => td.textContent))
      .find(cells => cells.includes("LEC内测-1元") && cells.includes("2026-10-06")),
    pressed: ["dailyChannelAggregateButton", "toggleDailyButton"].map(id => document.getElementById(id)?.getAttribute("aria-pressed")),
  }));
  if (!channelDate.title?.includes("渠道聚合 · 日数据")
      || JSON.stringify(channelDate.headers) !== JSON.stringify(["学部", "期次", "渠道展示", "下单日期", "当日现状"])
      || channelDate.row?.[4] !== "5"
      || channelDate.pressed.some(value => value !== "true")) {
    throw new Error(`channel and daily selections did not combine: ${JSON.stringify(channelDate)}`);
  }

  await page.evaluate(() => {
    for (const id of ["filterDepartment", "filterOrderDate"]) {
      const input = document.querySelector(`#${id} input:checked`);
      input.checked = false;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });
  const grouped = await page.evaluate(() => ({
    rows: [...document.querySelectorAll("#summaryBody tr")].map(tr => [...tr.querySelectorAll("td")].map(td => td.textContent)),
    summary: document.getElementById("filteredSummary")?.innerText,
  }));
  const primaryOctober7 = grouped.rows.find(row => row[0] === "小学" && row[2] === "测试渠道-1元" && row[3] === "2026-10-07");
  if (primaryOctober7?.[4] !== "2" || !grouped.summary?.includes("当日进量")) {
    throw new Error(`channel/date daily totals are wrong: ${JSON.stringify(grouped)}`);
  }

  const downloadPromise = page.waitForEvent("download");
  await page.click("#exportCurrent");
  const download = await downloadPromise;
  const csv = await readFile(await download.path(), "utf8");
  if (!csv.includes("学部,期次,渠道展示,下单日期,当日现状")
      || !csv.includes('"小学","秋_5","测试渠道-1元","2026-10-07","2"')
      || csv.includes("招生目标")) {
    throw new Error(`combined-view CSV does not match daily table: ${csv.slice(0, 500)}`);
  }

  await page.click("#dailyGradeAggregateButton");
  const threeDimensions = await page.evaluate(() => ({
    headers: [...document.querySelectorAll("#summaryHead th")].map(cell => cell.textContent),
    rows: [...document.querySelectorAll("#summaryBody tr")].map(tr => [...tr.querySelectorAll("td")].map(td => td.textContent)),
    pressed: ["dailyChannelAggregateButton", "dailyGradeAggregateButton", "toggleDailyButton"]
      .map(id => document.getElementById(id)?.getAttribute("aria-pressed")),
  }));
  if (JSON.stringify(threeDimensions.headers) !== JSON.stringify(["学部", "期次", "渠道展示", "年级", "下单日期", "当日现状"])
      || threeDimensions.rows.filter(row => row[0] === "小学" && row[2] === "测试渠道-1元" && row[4] === "2026-10-07").length !== 2
      || threeDimensions.pressed.some(value => value !== "true")) {
    throw new Error(`three selected dimensions are wrong: ${JSON.stringify(threeDimensions)}`);
  }

  await page.click("#toggleDailyButton");
  const cumulative = await page.evaluate(() => ({
    headers: [...document.querySelectorAll("#summaryHead th")].map(cell => cell.textContent),
    pressed: ["dailyChannelAggregateButton", "dailyGradeAggregateButton", "toggleDailyButton"]
      .map(id => document.getElementById(id)?.getAttribute("aria-pressed")),
  }));
  if (!cumulative.headers.includes("招生目标") || cumulative.headers.includes("下单日期")
      || JSON.stringify(cumulative.pressed) !== JSON.stringify(["true", "true", "false"])) {
    throw new Error(`daily toggle did not preserve aggregation dimensions: ${JSON.stringify(cumulative)}`);
  }
} finally {
  await browser.close();
}
