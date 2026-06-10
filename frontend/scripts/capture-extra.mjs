// 추가 클린 스크린샷 3종: 빈 진입 / (모달은 기존 재사용) / 시간표 그리드 크롭.
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const out = join(__dirname, "..", "screenshots");
const BASE = process.env.BASE_URL ?? "http://localhost:3001";
const DUMMY = [
  "2026 산업데이터공학과 전체성적조회",
  "데이터사이언스 3 A0",
  "기계학습1 3 B+",
  "데이터베이스설계 3 A-",
  "시계열분석 3 B0",
  "경제성분석 3 A0",
].join("\n");

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: "light",
});
const page = await ctx.newPage();
await page.addInitScript(() =>
  window.localStorage.setItem("course-fit-theme", "light"),
);

// 1) 빈 진입 (텍스트 입력 전)
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(500);
await page.screenshot({ path: join(out, "screen-3-empty.png"), fullPage: true });
console.log("saved screen-3-empty.png");

// 2) 결과 상태 → 시간표 그리드 카드만 크롭
await page.fill("textarea", DUMMY);
await page
  .getByRole("radio", { name: /데이터 분석가/ })
  .waitFor({ timeout: 8000 })
  .catch(() => {});
await page
  .getByRole("radio", { name: /데이터 분석가/ })
  .click()
  .catch((e) => console.log("job click:", String(e).split("\n")[0]));
await page.waitForTimeout(1800);
const gridCard = page
  .getByText("과목을 누르면 역량이 보여요")
  .locator('xpath=ancestor::div[contains(@class,"shadow-card")][1]');
await gridCard.scrollIntoViewIfNeeded().catch(() => {});
await page.waitForTimeout(400);
await gridCard
  .screenshot({ path: join(out, "screen-5-timetable.png") })
  .catch((e) => console.log("grid shot fail:", String(e).split("\n")[0]));
console.log("saved screen-5-timetable.png");

await browser.close();
console.log("done");
