import fs from "node:fs/promises";
import { chromium } from "playwright";

const manifestPath = "/Users/kityhello/workplace/project/rizhuizong/reports/daily_progress/manifest.json";
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));

const browser = await chromium.launch({ headless: true, channel: "chrome" });
for (const item of manifest) {
  const page = await browser.newPage({ viewport: { width: 1272, height: 1800 }, deviceScaleFactor: 1 });
  await page.goto(`file://${item.html}`);
  const box = await page.locator(".report").boundingBox();
  await page.screenshot({
    path: item.png,
    clip: {
      x: 0,
      y: 0,
      width: Math.ceil(box.width),
      height: Math.ceil(box.height),
    },
  });
  await page.close();
}
await browser.close();
