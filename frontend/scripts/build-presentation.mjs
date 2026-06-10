// 발표용 "주석 보드" 4장 생성기.
// 제품 스크린샷(raw/*.png)을 배경 카드로 깔고, 실제 요소 좌표(boxes.json)에
// 맞춰 번호 핀 + 연결선 + 라벨 카드 + 상단 제목을 얹어 다시 스크린샷 → PNG.
// 앱 코드는 읽기만 한다. 출력: frontend/presentation/{00..03}-*.png
import { chromium } from "playwright";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const rawDir = join(root, "presentation", "raw");
const outDir = join(root, "presentation");

const boxes = JSON.parse(readFileSync(join(rawDir, "boxes.json"), "utf8"));
const b64 = (p) => readFileSync(p).toString("base64");
const pretendard = b64(join(root, "app", "fonts", "PretendardVariable.woff2"));
const shotA = b64(join(rawDir, "stateA.png")); // 1440x1275 CSS (DPR2)
const shotB = b64(join(rawDir, "stateB.png")); // 1440x2047 CSS (DPR2)

// 제품 토큰 (globals.css 와 동일)
const C = {
  bg: "oklch(0.985 0.005 85)", // 보드 배경: 제품보다 살짝 더 깊은 warm
  board: "oklch(0.992 0.004 85)",
  ink: "oklch(0.245 0.006 70)",
  inkMuted: "oklch(0.52 0.006 70)",
  inkSubtle: "oklch(0.66 0.007 72)",
  line: "oklch(0.9 0.006 75)",
  lineStrong: "oklch(0.83 0.008 74)",
  accent: "oklch(0.55 0.12 152)",
  accentStrong: "oklch(0.48 0.13 152)",
  accentWash: "oklch(0.955 0.03 152)",
  surface: "oklch(1 0.002 85)",
  connector: "oklch(0.74 0.008 74)", // 차분한 회색 연결선
};

const FONT_FACE = `
@font-face{
  font-family:'Pretendard';
  src:url('data:font/woff2;base64,${pretendard}') format('woff2');
  font-weight:100 900; font-display:block; font-style:normal;
}`;

// 공통 스타일
const baseCSS = `
${FONT_FACE}
*{margin:0;padding:0;box-sizing:border-box;}
html,body{font-family:'Pretendard',-apple-system,system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;}
.board{position:relative;background:${C.bg};overflow:hidden;}
/* 상단 헤더 */
.kicker{display:inline-flex;align-items:center;gap:8px;font-size:15px;font-weight:600;
  letter-spacing:.02em;color:${C.accentStrong};}
.kicker .dot{width:7px;height:7px;border-radius:50%;background:${C.accent};display:inline-block;}
.title{font-weight:800;color:${C.ink};letter-spacing:-0.022em;line-height:1.12;}
.subtitle{color:${C.inkMuted};font-weight:500;letter-spacing:-0.01em;}
.brand{position:absolute;display:flex;align-items:center;gap:9px;color:${C.inkSubtle};
  font-weight:700;font-size:18px;letter-spacing:-0.01em;}
.brand .mark{width:13px;height:13px;border-radius:4px;background:${C.accent};
  box-shadow:0 0 0 4px ${C.accentWash};}
/* 스크린샷을 담는 브라우저 프레임 카드 */
.frame{position:absolute;background:${C.surface};border:1px solid ${C.line};
  border-radius:16px;box-shadow:0 1px 0 ${C.line},0 22px 50px -28px oklch(0.4 0.02 75 / .35),
  0 6px 16px -10px oklch(0.4 0.02 75 / .18);overflow:hidden;}
.frame .bar{height:34px;background:oklch(0.975 0.004 80);border-bottom:1px solid ${C.line};
  display:flex;align-items:center;gap:7px;padding:0 14px;}
.frame .bar i{width:10px;height:10px;border-radius:50%;background:${C.line};display:block;}
.frame .bar .url{margin-left:12px;height:18px;flex:1;max-width:360px;border-radius:6px;
  background:${C.bg};border:1px solid ${C.line};display:flex;align-items:center;
  padding:0 10px;font-size:11px;color:${C.inkSubtle};font-weight:500;}
.shot{display:block;background-repeat:no-repeat;background-size:100% auto;}
/* 콜아웃 */
.pin{position:absolute;width:30px;height:30px;border-radius:50%;
  background:${C.accent};color:#fff;font-weight:800;font-size:15px;
  display:flex;align-items:center;justify-content:center;z-index:6;
  box-shadow:0 0 0 4px ${C.board},0 0 0 6px ${C.accentWash},
  0 6px 14px -4px oklch(0.45 0.13 152 / .5);}
.pin.sm{width:26px;height:26px;font-size:13px;}
.label{position:absolute;background:${C.surface};border:1px solid ${C.line};
  border-radius:13px;padding:15px 17px 16px;z-index:5;
  box-shadow:0 14px 34px -20px oklch(0.4 0.02 75 / .4),0 2px 6px -3px oklch(0.4 0.02 75 / .15);}
.label .head{display:flex;align-items:center;gap:9px;margin-bottom:7px;}
.label .num{width:21px;height:21px;border-radius:6px;background:${C.accentWash};
  color:${C.accentStrong};font-weight:800;font-size:12px;display:flex;
  align-items:center;justify-content:center;flex:none;}
.label .t{font-weight:700;color:${C.ink};font-size:16.5px;letter-spacing:-0.01em;line-height:1.3;}
.label .d{color:${C.inkMuted};font-size:13.5px;line-height:1.5;font-weight:450;letter-spacing:-0.005em;}
.label.compact .t{font-size:15.5px;}
svg.wires{position:absolute;inset:0;z-index:4;pointer-events:none;overflow:visible;}
.wire{fill:none;stroke:${C.connector};stroke-width:1.6;}
.wire-dot{fill:${C.connector};}
`;

const browser = await chromium.launch();

// 보드 1장 렌더 → PNG. spec.html 은 .board 내부 마크업.
async function render({ file, W, H, html }) {
  const ctx = await browser.newContext({
    viewport: { width: W, height: H },
    deviceScaleFactor: 2,
    colorScheme: "light",
  });
  const page = await ctx.newPage();
  await page.setContent(
    `<!doctype html><html><head><meta charset="utf8"><style>${baseCSS}</style></head>
     <body><div class="board" style="width:${W}px;height:${H}px">${html}</div></body></html>`,
    { waitUntil: "load" },
  );
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(250);
  await page.locator(".board").screenshot({ path: join(outDir, file) });
  await ctx.close();
  console.log("saved", file);
}

// ─── 헬퍼: 스크린샷 일부를 잘라 보여주는 .shot 박스 ──────────────────
// natW: 원본 CSS 너비(1440). frame 안에서 scale 배율로 보여준다.
// crop: {x,y,w,h} CSS px. 화면에 cw x ch 로 그린다.
function shotBox({ shot, natW, crop, left, top, cw }) {
  const scale = cw / crop.w;
  const ch = crop.h * scale;
  const bgW = natW * scale;
  const bgX = -crop.x * scale;
  const bgY = -crop.y * scale;
  return {
    html: `<div class="shot" style="position:absolute;left:${left}px;top:${top}px;
      width:${cw}px;height:${ch}px;
      background-image:url('data:image/png;base64,${shot}');
      background-size:${bgW}px auto;background-position:${bgX}px ${bgY}px;"></div>`,
    ch,
    scale,
  };
}

// ════════════════════════════════════════════════════════════════
// SLIDE 00 - 전체 사용자 흐름 (4단계 썸네일 + 화살표)
// ════════════════════════════════════════════════════════════════
async function slide00() {
  const W = 1760,
    H = 990;
  const ib = boxes.input,
    rb = boxes.result;
  // 4개의 세로 카드(썸네일)를 균등 배치
  const cardW = 332,
    gap = 64,
    top = 360;
  const startX = (W - (cardW * 4 + gap * 3)) / 2;
  const xs = [0, 1, 2, 3].map((i) => startX + i * (cardW + gap));

  const steps = [
    {
      n: "①",
      label: "성적표 붙여넣기",
      sub: "텍스트만 붙여넣으면 시작",
      shot: shotA,
      crop: { x: 196, y: 446, w: 1048, h: 250 }, // 붙여넣은 textarea (그린 보더)
    },
    {
      n: "②",
      label: "자동 인식",
      sub: "학번 / 학점 / GPA / 과목수",
      shot: shotA,
      crop: { x: 210, y: 560, w: 820, h: 250 }, // 인식 칩 줄 클로즈업
    },
    {
      n: "③",
      label: "목표 직무 선택",
      sub: "학생이 직접 고름",
      shot: shotB, // 선택된 카드(그린 체크)가 보이도록 결과 상태 화면 사용
      crop: { x: 196, y: 776, w: 1048, h: 280 }, // 직무 카드 그리드 (데이터 분석가 선택됨)
    },
    {
      n: "④",
      label: "추천 시간표",
      sub: "시간 충돌 0",
      shot: shotB,
      crop: { x: 196, y: 1290, w: 1048, h: 560 }, // 시간표 그리드
    },
  ];

  const thumbCh = 250; // 썸네일 표시 높이
  let cards = "";
  let wires = "";
  steps.forEach((s, i) => {
    const x = xs[i];
    const sb = shotBox({
      shot: s.shot,
      natW: 1440,
      crop: s.crop,
      left: 0,
      top: 0,
      cw: cardW - 2,
    });
    const isWide = i === 3;
    cards += `
    <div style="position:absolute;left:${x}px;top:${top}px;width:${cardW}px;">
      <div class="frame" style="position:relative;left:0;top:0;width:${cardW}px;border-radius:14px;">
        <div class="bar" style="height:26px;"><i></i><i></i><i></i></div>
        <div style="position:relative;width:${cardW}px;height:${thumbCh}px;overflow:hidden;">
          ${sb.html.replace('left:0px;top:0px;', `left:0px;top:0px;`)}
          ${isWide ? `<div style="position:absolute;right:10px;top:10px;background:${C.accent};color:#fff;font-size:12px;font-weight:800;padding:5px 11px;border-radius:999px;box-shadow:0 4px 12px -4px oklch(.45 .13 152/.5);">충돌 0</div>` : ""}
        </div>
      </div>
      <div style="margin-top:22px;display:flex;align-items:flex-start;gap:11px;">
        <div style="font-size:22px;font-weight:800;color:${C.accent};line-height:1;flex:none;margin-top:1px;">${s.n}</div>
        <div>
          <div style="font-size:21px;font-weight:800;color:${C.ink};letter-spacing:-0.02em;line-height:1.2;">${s.label}</div>
          <div style="font-size:14.5px;color:${C.inkMuted};font-weight:500;margin-top:4px;letter-spacing:-0.005em;">${s.sub}</div>
        </div>
      </div>
    </div>`;
    // 카드 사이 화살표
    if (i < 3) {
      const ax = x + cardW + 8;
      const ay = top + thumbCh / 2 + 13;
      wires += `<g>
        <line x1="${ax}" y1="${ay}" x2="${ax + gap - 16}" y2="${ay}" stroke="${C.connector}" stroke-width="2"/>
        <path d="M ${ax + gap - 16} ${ay} l -8 -5 v 10 z" fill="${C.connector}"/>
      </g>`;
    }
  });

  const html = `
    <div class="brand" style="left:64px;top:52px;"><span class="mark"></span>course-fit</div>
    <div style="position:absolute;left:64px;top:128px;right:64px;">
      <div class="kicker"><span class="dot"></span>USER FLOW</div>
      <div class="title" style="font-size:58px;margin-top:18px;">성적표 한 번이면, 직무 맞춤 시간표까지</div>
      <div class="subtitle" style="font-size:21px;margin-top:16px;">붙여넣기에서 추천까지, 한 화면에서 순차로 펼쳐지는 4단계.</div>
    </div>
    <svg class="wires" viewBox="0 0 ${W} ${H}">${wires}</svg>
    ${cards}
    <div style="position:absolute;left:0;right:0;bottom:42px;text-align:center;font-size:14px;color:${C.inkSubtle};font-weight:500;letter-spacing:-0.005em;">데모 데이터 기준 예시 화면입니다.</div>
  `;
  await render({ file: "00-flow.png", W, H, html });
}

// ════════════════════════════════════════════════════════════════
// 공통: 큰 스크린샷을 프레임에 담아 보드 좌측에 배치하고,
// 우측/좌측 여백에 라벨을 두며 연결선을 긋는 슬라이드 레이아웃.
// boxesScope: 'input' | 'result' 의 좌표를 사용.
// callouts: [{n,t,d, anchor:{x,y(px CSS, 페이지 좌표)}, side:'right'|'left', labelTop}]
// ════════════════════════════════════════════════════════════════
async function annotatedSlide({
  file,
  kicker,
  title,
  subtitle,
  shot,
  crop, // {x,y,w,h} 보여줄 화면 영역 (CSS px)
  frameLeft,
  frameTop,
  frameW, // 프레임 표시 너비
  callouts,
  W,
  H,
}) {
  const scale = frameW / crop.w; // 화면→보드 배율
  const barH = 34;
  const shotTop = frameTop + barH;
  const sb = shotBox({
    shot,
    natW: 1440,
    crop,
    left: frameLeft,
    top: shotTop,
    cw: frameW,
  });
  const frameH = barH + sb.ch;
  // 보드 높이를 프레임에 맞춰 자동 계산(하단 빈 공간 제거)
  H = Math.round(frameTop + frameH + 72);

  // 페이지 좌표(CSS) → 보드 좌표(px)
  const toBoardX = (px) => frameLeft + (px - crop.x) * scale;
  const toBoardY = (py) => shotTop + (py - crop.y) * scale;

  // 모든 라벨은 우측 거터에 세로로 쌓는다(좌측 클리핑 방지, 시선 동선 단순화).
  const lblW = 350;
  const gutterX = frameLeft + frameW + 70; // 라벨 좌측 시작
  const stackTop = frameTop + 2;
  const stackBottom = frameTop + frameH - 2;
  const n = callouts.length;
  // 핀 Y 순서대로 슬롯을 배정해 연결선 교차를 최소화
  const order = callouts.map((c, i) => i).sort(
    (a, e) => toBoardY(callouts[a].anchor.y) - toBoardY(callouts[e].anchor.y),
  );
  const slotGap = (stackBottom - stackTop) / n;
  const slotY = {}; // callout index -> 라벨 top
  order.forEach((ci, slot) => {
    slotY[ci] = Math.round(stackTop + slot * slotGap + (slotGap - 96) / 2);
  });

  let pins = "",
    labels = "",
    wires = "";
  callouts.forEach((c, i) => {
    const px = toBoardX(c.anchor.x);
    const py = toBoardY(c.anchor.y);
    pins += `<div class="pin" style="left:${px - 15}px;top:${py - 15}px;">${i + 1}</div>`;

    const lblX = gutterX;
    const lblY = slotY[i];
    labels += `
      <div class="label ${c.compact ? "compact" : ""}" style="left:${lblX}px;top:${lblY}px;width:${lblW}px;">
        <div class="head"><span class="num">${i + 1}</span><span class="t">${c.t}</span></div>
        ${c.d ? `<div class="d">${c.d}</div>` : ""}
      </div>`;

    // 연결선: 핀 → 라벨 카드 좌측 모서리. 거터 직전에서 수평으로 꺾는 elbow.
    const lblAnchorX = lblX;
    const lblAnchorY = lblY + 26;
    const elbowX = frameLeft + frameW + 30; // 프레임 밖에서 꺾기
    wires += `
      <path class="wire" d="M ${px} ${py} H ${elbowX} V ${lblAnchorY} H ${lblAnchorX - 6}"/>
      <circle class="wire-dot" cx="${px}" cy="${py}" r="3.2"/>`;
  });

  const html = `
    <div class="brand" style="left:64px;top:52px;"><span class="mark"></span>course-fit</div>
    <div style="position:absolute;left:64px;top:120px;right:64px;">
      <div class="kicker"><span class="dot"></span>${kicker}</div>
      <div class="title" style="font-size:46px;margin-top:15px;">${title}</div>
      ${subtitle ? `<div class="subtitle" style="font-size:19px;margin-top:13px;">${subtitle}</div>` : ""}
    </div>
    <div class="frame" style="left:${frameLeft}px;top:${frameTop}px;width:${frameW}px;height:${frameH}px;">
      <div class="bar"><i></i><i></i><i></i><span class="url">localhost / course-fit</span></div>
    </div>
    ${sb.html}
    <svg class="wires" viewBox="0 0 ${W} ${H}">${wires}</svg>
    ${pins}
    ${labels}
  `;
  await render({ file, W, H, html });
}

// ════════════════════════════════════════════════════════════════
// SLIDE 01 - 입력 / 가이드 화면
// ════════════════════════════════════════════════════════════════
async function slide01() {
  const ib = boxes.input;
  const W = 1760,
    H = 1180;
  const frameLeft = 96,
    frameTop = 300,
    frameW = 1040;
  const crop = { x: 184, y: 250, w: 1072, h: 470 }; // 가이드 + textarea + 칩

  await annotatedSlide({
    file: "01-input.png",
    kicker: "STEP 01 / 입력",
    title: "성적표 붙여넣기 한 번으로 시작",
    subtitle: "학교 성적 페이지를 그대로 복사해 붙여넣으면 됩니다. 별도 입력 폼이 없습니다.",
    shot: shotA,
    crop,
    frameLeft,
    frameTop,
    frameW,
    W,
    H,
    callouts: [
      {
        t: "성적 조회 가이드 내장",
        d: "마이홍익 포털 링크 + 화면 미리보기를 화면 안에서 바로 안내합니다.",
        anchor: { x: ib.myhongik?.x + 30 || 290, y: ib.myhongik?.y + 11 || 343 },
        side: "right",
        labelTop: 318,
        w: 326,
      },
      {
        t: "붙여넣기 한 번으로 시작",
        d: "성적표 텍스트를 그대로 붙여넣는 단일 입력. 학생이 칸마다 입력할 필요가 없습니다.",
        anchor: { x: ib.textarea.x + 260, y: ib.textarea.y + 70 },
        side: "right",
        labelTop: 560,
        w: 326,
      },
      {
        t: "빈 입력은 점선, 인식되면 강조",
        d: "상태 전환으로 다음 행동을 유도합니다. 인식되면 테두리가 그린으로 살아납니다.",
        anchor: { x: ib.chipRow.x + ib.chipRow.w - 30, y: ib.chipRow.y + 14 },
        side: "left",
        labelTop: 600,
        w: 318,
      },
    ],
  });
}

// ════════════════════════════════════════════════════════════════
// SLIDE 02 - 인식 + 직무 선택
// ════════════════════════════════════════════════════════════════
async function slide02() {
  const ib = boxes.input;
  const W = 1760,
    H = 1220;
  const frameLeft = 96,
    frameTop = 300,
    frameW = 1040;
  const crop = { x: 184, y: 620, w: 1072, h: 480 }; // 칩 줄 + 직무 카드 + 잘 모르겠어요

  await annotatedSlide({
    file: "02-recognize-job.png",
    kicker: "STEP 02 / 인식과 선택",
    title: "제대로 읽었다는 신호, 그리고 직접 고르는 목표",
    subtitle: "자동 인식으로 신뢰를 주고, 목표 직무는 학생이 명시적으로 선택합니다.",
    shot: shotA,
    crop,
    frameLeft,
    frameTop,
    frameW,
    W,
    H,
    callouts: [
      {
        t: "학번 / 학점 / GPA / 과목수 자동 인식",
        d: "붙여넣으면 핵심 항목을 즉시 칩으로 보여줍니다. 제대로 읽었다는 신뢰 신호.",
        anchor: { x: ib.chipRow.x + ib.chipRow.w - 60, y: ib.chipRow.y + 14 },
        side: "right",
        labelTop: 330,
        w: 332,
      },
      {
        t: "목표 직무는 학생이 직접 선택",
        d: "추천이 아니라 명시적 선택. 진로의 주도권을 학생에게 둡니다.",
        anchor: { x: ib.jobDА.x + ib.jobDА.w - 40, y: ib.jobDА.y + 40 },
        side: "right",
        labelTop: 600,
        w: 332,
      },
      {
        t: "진로 미정이면 ‘잘 모르겠어요’",
        d: "아직 직무를 못 정한 학생을 위한 안내 경로를 따로 둡니다.",
        anchor: { x: ib.unsure.x + 50, y: ib.unsure.y + 10 },
        side: "left",
        labelTop: 640,
        w: 318,
      },
    ],
  });
}

// ════════════════════════════════════════════════════════════════
// SLIDE 03 - 추천 결과 (핵심)
// ════════════════════════════════════════════════════════════════
async function slide03() {
  const rb = boxes.result;
  const W = 1760,
    H = 1320;
  const frameLeft = 96,
    frameTop = 300,
    frameW = 1056;
  const crop = { x: 184, y: 1108, w: 1072, h: 770 }; // 토글 + 결과 heading + 그리드 + 추천목록

  await annotatedSlide({
    file: "03-result.png",
    kicker: "STEP 03 / 추천 결과",
    title: "충돌 0, 적합도 최대. 그리고 ‘왜’까지 보여줍니다",
    subtitle: "ILP 최적화로 짠 다음 학기 시간표. 핵심부터 보여주고 깊은 정보는 접어둡니다.",
    shot: shotB,
    crop,
    frameLeft,
    frameTop,
    frameW,
    W,
    H,
    callouts: [
      {
        t: "상단 직무 토글로 즉시 비교",
        d: "다른 직무를 누르면 시간표가 바로 바뀝니다. switch and see.",
        anchor: { x: rb.toggle.x + rb.toggle.w - 120, y: rb.toggle.y + 21 },
        side: "right",
        labelTop: 322,
        w: 330,
      },
      {
        t: "ILP 최적화: 충돌 0 + 적합도 최대",
        d: "시간 충돌 없이 직무 적합도를 최대화한 다음 학기 시간표를 자동 구성합니다.",
        anchor: { x: rb.resultHeading.x + rb.resultHeading.w + 40, y: rb.resultHeading.y + 20 },
      },
      {
        t: "과목을 누르면 근거 제시",
        d: "어떤 역량을 채우는 과목인지 보여주는 설명 가능한 추천.",
        anchor: { x: rb.firstCourse.x + 54, y: rb.firstCourse.y + 70 },
        side: "left",
        labelTop: 590,
        w: 318,
      },
      {
        t: "깊은 정보는 펼침",
        d: "역량 차트 / 졸업 진척은 접어두고, 핵심부터 보여줍니다.",
        anchor: { x: rb.gridArea.x + 90, y: rb.gridArea.y + rb.gridArea.h - 18 },
        side: "left",
        labelTop: 900,
        w: 318,
      },
    ],
  });
}

await slide00();
await slide01();
await slide02();
await slide03();

await browser.close();
console.log("ALL DONE");
