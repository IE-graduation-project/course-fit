// 발표용 최종 컷 (채택된 A 디자인, 메인 라우트 /).
// idle 은 모션 ON(자기 타이핑 보이게), 나머지는 reducedMotion(카운트업 최종값 확정).
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const out = join(__dirname, "..", "final");
mkdirSync(out, { recursive: true });
const BASE = process.env.BASE_URL ?? "http://localhost:3001";
const DUMMY = [
  "2026 산업데이터공학과 전체성적조회",
  "데이터사이언스 3 A0",
  "기계학습1 3 B+",
  "데이터베이스설계 3 A-",
  "시계열분석 3 B0",
  "경제성분석 3 A0",
].join("\n");
const HIDE = "nextjs-portal{display:none!important}";

const browser = await chromium.launch();

async function mk(reduced) {
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    colorScheme: "light",
    reducedMotion: reduced ? "reduce" : "no-preference",
  });
  const page = await ctx.newPage();
  await page.addInitScript(() =>
    window.localStorage.setItem("course-fit-theme", "light"),
  );
  return { ctx, page };
}
async function prep(page) {
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: HIDE }).catch(() => {});
}
async function shot(page, name, ms) {
  await page.waitForTimeout(ms);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(250);
  await page.screenshot({ path: join(out, name), fullPage: true });
  console.log("saved", name);
}

// 1) idle (모션 ON: 자기 타이핑)
{
  const { ctx, page } = await mk(false);
  await prep(page);
  await shot(page, "1-idle.png", 2000);
  await ctx.close();
}

// 2~4) 인식+직무 / 결과 / 직무전환 (reduce)
{
  const { ctx, page } = await mk(true);
  await prep(page);
  await page.fill("textarea", DUMMY);
  await page.getByRole("radio", { name: /데이터 분석가/ }).waitFor({ timeout: 9000 }).catch(() => {});
  await shot(page, "2-recognized-jobs.png", 1400);

  await page.getByRole("radio", { name: /데이터 분석가/ }).click().catch(() => {});
  await shot(page, "3-result-analyst.png", 1500);

  // switch and see: 데이터 사이언티스트로 전환 (시간표/점수가 바뀜)
  await page.getByRole("tab", { name: /데이터 사이언티스트/ }).click().catch(() => {});
  await shot(page, "4-result-scientist.png", 1500);
  await ctx.close();
}

await browser.close();
console.log("done");
