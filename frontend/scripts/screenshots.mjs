import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = join(__dirname, "..", "screenshots");
mkdirSync(outDir, { recursive: true });

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const WIDTH = 1440;

// 발표용 더미 성적표 (mock: 글자만 있으면 인식됨)
const DUMMY_TRANSCRIPT = [
  "2026 산업데이터공학과 전체성적조회",
  "데이터사이언스 3 A0",
  "기계학습1 3 B+",
  "데이터베이스설계 3 A-",
  "시계열분석 3 B0",
  "경제성분석 3 A0",
].join("\n");

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: WIDTH, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: "light",
});
const page = await context.newPage();
// 발표용 기본은 라이트 모드로 고정
await page.addInitScript(() =>
  window.localStorage.setItem("course-fit-theme", "light"),
);

await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);

// ── ① 진입 상태: 성적표 입력 + 인식 후 직무 카드 노출 ──────────────
await page.fill("textarea", DUMMY_TRANSCRIPT);
// 인식 칩 + 직무 카드가 나타날 때까지 대기
await page
  .getByRole("radiogroup", { name: "목표 직무" })
  .waitFor({ timeout: 8000 })
  .catch(() => console.warn("job radiogroup not found, continuing"));
await page.waitForTimeout(1200);
// 자동 스크롤(직무 영역 안내) 이후 맨 위로 되돌려 sticky 헤더 겹침 방지
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(400);
await page.screenshot({ path: join(outDir, "main.png"), fullPage: true });
console.log("saved main.png");

// ── ② 직무 선택 후 결과: 그리드 + 직무 토글 + 요약 ─────────────────
await page.getByRole("radio", { name: /데이터 분석가/ }).click();
// 직무 토글 바(switch and see)가 나타날 때까지 대기
await page
  .getByRole("tablist", { name: "직무 전환" })
  .waitFor({ timeout: 8000 })
  .catch(() => console.warn("job toggle bar not found, continuing"));
// 점수 카운트 + 그리드 진입 애니메이션 안정화
await page.waitForTimeout(1600);
// fullPage 합성 시 sticky 헤더가 중간에 떠 보이지 않도록 맨 위로
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(400);
await page.screenshot({ path: join(outDir, "result.png"), fullPage: true });
console.log("saved result.png");

await browser.close();
console.log("done");
