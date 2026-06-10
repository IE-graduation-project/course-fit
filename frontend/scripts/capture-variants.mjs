// 변형 비교 캡처: /(기준) /va(모핑) /vc(자가시연) × 3상태.
// 빈 진입(idle)은 모션 ON 으로 떠서 유령 시간표/자기 타이핑이 보이게 하고,
// 인식+직무 / 결과는 reducedMotion 으로 떠서 RAF 카운트업이 최종값으로 확정되게 한다
// (정지컷이므로 모션 중간 프레임보다 확정된 최종 프레임이 완성도 높다).
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const out = join(__dirname, "..", "compare");
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

const ROUTES = [
  { path: "/", tag: "base" },
  { path: "/va", tag: "va" },
  { path: "/vc", tag: "vc" },
];

const HIDE_OVERLAY = "nextjs-portal{display:none!important}";

const browser = await chromium.launch();

async function newPage(reduced) {
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

async function prep(page, path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: HIDE_OVERLAY }).catch(() => {});
}

async function settle(page, ms) {
  await page.waitForTimeout(ms);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(250);
}

// ── ① 빈 진입 (모션 ON: 유령 시간표 / 자기 타이핑이 보이게) ──
{
  const { ctx, page } = await newPage(false);
  for (const r of ROUTES) {
    await prep(page, r.path);
    await settle(page, 2000); // 유령 블록이 떠오를 시간
    await page.screenshot({
      path: join(out, `${r.tag}-1-idle.png`),
      fullPage: true,
    });
    console.log(`saved ${r.tag}-1-idle.png`);
  }
  await ctx.close();
}

// ── ②③ 인식+직무 / 결과 (reducedMotion: 카운트업 최종값 확정) ──
{
  const { ctx, page } = await newPage(true);
  for (const r of ROUTES) {
    await prep(page, r.path);

    await page.fill("textarea", DUMMY);
    await page
      .getByRole("radio", { name: /데이터 분석가/ })
      .waitFor({ timeout: 9000 })
      .catch(() => console.warn(`${r.tag}: job radio not found`));
    await settle(page, 1400);
    await page.screenshot({
      path: join(out, `${r.tag}-2-jobs.png`),
      fullPage: true,
    });
    console.log(`saved ${r.tag}-2-jobs.png`);

    await page
      .getByRole("radio", { name: /데이터 분석가/ })
      .click()
      .catch((e) => console.warn(`${r.tag}: click fail`, String(e).split("\n")[0]));
    await settle(page, 1600);
    await page.screenshot({
      path: join(out, `${r.tag}-3-result.png`),
      fullPage: true,
    });
    console.log(`saved ${r.tag}-3-result.png`);
  }
  await ctx.close();
}

await browser.close();
console.log("done");
