// 가이드 "미리보기" hover 팝오버 열린 상태 캡처 (보여주기용).
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = join(__dirname, "..", "screenshots");
const BASE = process.env.BASE_URL ?? "http://localhost:3001";

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 1120 },
  deviceScaleFactor: 2,
  colorScheme: "light",
});
const page = await ctx.newPage();
await page.addInitScript(() =>
  window.localStorage.setItem("course-fit-theme", "light"),
);
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);

const btn = page.getByRole("button", { name: /미리보기/ });
await btn.scrollIntoViewIfNeeded().catch(() => {});
await btn.click().catch((e) => console.warn("click fail", String(e).split("\n")[0]));
await page.waitForTimeout(700);
await page.screenshot({ path: join(outDir, "guide-modal.png") });
console.log("saved guide-modal.png");

await browser.close();
console.log("done");
