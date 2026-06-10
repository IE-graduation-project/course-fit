// 발표용 주석 보드의 "배경"이 될 제품 스크린샷 + 콜아웃을 꽂을 요소들의
// 실제 좌표(bbox)를 함께 기록한다. 앱 코드는 건드리지 않고 캡처/측정만 한다.
// 출력: frontend/presentation/raw/*.png  +  frontend/presentation/raw/boxes.json
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const rawDir = join(__dirname, "..", "presentation", "raw");
mkdirSync(rawDir, { recursive: true });

const BASE = process.env.BASE_URL ?? "http://localhost:3001";
const WIDTH = 1440;
const DPR = 2;

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
  viewport: { width: WIDTH, height: 900 },
  deviceScaleFactor: DPR,
  colorScheme: "light",
});
const page = await ctx.newPage();
await page.addInitScript(() =>
  window.localStorage.setItem("course-fit-theme", "light"),
);
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);

// 측정 헬퍼: viewport 좌표계(CSS px) 기준 bbox 반환 (스크린샷이 fullPage라
// scrollY를 더해 페이지 좌표계로 변환한다)
async function boxOf(locator) {
  const b = await locator.first().boundingBox();
  if (!b) return null;
  const scrollY = await page.evaluate(() => window.scrollY);
  return {
    x: Math.round(b.x),
    y: Math.round(b.y + scrollY),
    w: Math.round(b.width),
    h: Math.round(b.height),
  };
}

const boxes = {};

// ──────────────────────────────────────────────────────────────
// STATE A: 입력 + 인식 (직무 선택 전). slide 01 / 02 / flow ①②
// ──────────────────────────────────────────────────────────────
await page.fill("textarea", DUMMY);
await page
  .getByRole("radiogroup", { name: "목표 직무" })
  .waitFor({ timeout: 8000 })
  .catch(() => {});
await page.waitForTimeout(900);
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(300);

boxes.input = {
  pageW: WIDTH,
  pageH: await page.evaluate(() => document.body.scrollHeight),
  guideToggle: await boxOf(page.getByRole("button", { name: "성적표 가져오는 방법" })),
  myhongik: await boxOf(page.getByRole("link", { name: /마이홍익/ })).catch(() => null),
  preview: await boxOf(page.getByRole("button", { name: /미리보기/ })),
  textarea: await boxOf(page.locator("textarea")),
  chips: await boxOf(page.getByText(/24과목 인식|GPA/).first()).catch(() => null),
  jobGroup: await boxOf(page.getByRole("radiogroup", { name: "목표 직무" })),
  jobDА: await boxOf(page.getByRole("radio", { name: /데이터 분석가/ })),
  unsure: await boxOf(page.getByRole("button", { name: /잘 모르겠어요/ })),
  h2input: await boxOf(page.getByRole("heading", { name: "성적표 붙여넣기" })),
  h2job: await boxOf(page.getByRole("heading", { name: "어떤 직무를 목표로 하나요?" })),
};
// chips 줄 전체를 잡기 위해 학번/학점/GPA 칩 컨테이너 추정
boxes.input.chipRow = await boxOf(
  page.locator("text=GPA").locator("xpath=ancestor::*[self::div][1]"),
).catch(() => null);

await page.screenshot({ path: join(rawDir, "stateA.png"), fullPage: true });
console.log("saved stateA.png");

// ──────────────────────────────────────────────────────────────
// STATE B: 직무 선택 후 결과. slide 03 / flow ④
// ──────────────────────────────────────────────────────────────
await page.getByRole("radio", { name: /데이터 분석가/ }).click();
await page
  .getByRole("tablist", { name: "직무 전환" })
  .waitFor({ timeout: 8000 })
  .catch(() => {});
await page.waitForTimeout(1700);
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(300);

boxes.result = {
  pageW: WIDTH,
  pageH: await page.evaluate(() => document.body.scrollHeight),
  toggle: await boxOf(page.getByRole("tablist", { name: "직무 전환" })),
  toggleActive: await boxOf(page.getByRole("tab", { name: /데이터 분석가/ })),
  resultHeading: await boxOf(page.getByRole("heading", { name: /맞춤 시간표/ })),
  grid: null,
  recommendList: null,
  firstCourse: await boxOf(page.getByRole("button", { name: /시계열분석/ })).catch(() => null),
};
// 시간표 그리드 컨테이너: 결과 heading 다음 큰 격자. heading 부모 section 안에서 추정
boxes.result.gridArea = await boxOf(
  page.getByRole("heading", { name: /맞춤 시간표/ }).locator("xpath=ancestor::section[1]"),
).catch(() => null);

await page.screenshot({ path: join(rawDir, "stateB.png"), fullPage: true });
console.log("saved stateB.png");

writeFileSync(join(rawDir, "boxes.json"), JSON.stringify(boxes, null, 2));
console.log("saved boxes.json");

await browser.close();
console.log("done");
