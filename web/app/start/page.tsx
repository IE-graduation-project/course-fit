"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { countCourseLines, fetchReference, submitTranscript } from "@/lib/api";
import { SAMPLE_TRANSCRIPT } from "@/lib/sample";
import type { JobRef, ModeRef, Reference } from "@/lib/types";
import { jobRank } from "@/lib/competency";

type Step = "transcript" | "job" | "mode" | "done";

/**
 * 성적표 입력 — 대화형.
 * 소연님 제안(6/10): "성적표 넣는 과정을 채팅처럼 재밌게, 시간표 결과는 정적으로".
 * 그래서 입력만 대화로 받고, 결과는 /result 에서 한 화면에 정적으로 보여준다.
 */
export default function StartPage() {
  const router = useRouter();
  const [ref, setRef] = useState<Reference | null>(null);
  const [step, setStep] = useState<Step>("transcript");
  const [text, setText] = useState("");
  const [job, setJob] = useState<JobRef | null>(null);
  const [mode, setMode] = useState<ModeRef | null>(null);
  const [courseCount, setCourseCount] = useState(0);
  const [deptLabel, setDeptLabel] = useState("경영학전공");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchReference().then(setRef).catch(console.error);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [step]);

  async function handleTranscript(value: string) {
    if (!value.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await submitTranscript({
        text: value,
        dept: "BIZ",
        admissionYear: 2022,
      });
      sessionStorage.setItem("studentId", res.studentId);
      setCourseCount(res.courseCount);
      setDeptLabel(res.deptId === "IDE" ? "산업데이터공학과" : "경영학전공");
      setText(value);
      setStep("job");
    } catch (e) {
      // 삼키면 사용자는 버튼을 눌렀는데 아무 일도 안 일어난 것으로 본다.
      console.error(e);
      setError("성적표를 읽는 중 문제가 생겼어요. 잠시 후 다시 눌러주세요.");
    } finally {
      setBusy(false);
    }
  }

  function handleJob(j: JobRef) {
    setJob(j);
    setStep("mode");
  }

  function handleMode(m: ModeRef) {
    setMode(m);
    setStep("done");
    setTimeout(() => {
      router.push(`/result?job=${job!.id}&mode=${m.id}`);
    }, 900);
  }

  return (
    // relative: 안의 sr-only(absolute)가 위치 기준을 못 찾으면
    // 초기 컨테이닝 블록에 놓여 문서 폭을 늘린다. JobFitBar 에서 실제로 그랬다.
    <main className="relative mx-auto min-h-dvh max-w-2xl px-5 py-8">
      <header className="mb-8 flex items-center justify-between">
        <Link href="/" className="-ml-2 inline-flex min-h-11 items-center rounded-sm px-2 text-sm font-semibold text-text-muted hover:text-text">
          ← course-fit
        </Link>
        <StepDots step={step} />
      </header>

      <h1 className="sr-only">성적표 입력</h1>

      <div className="space-y-5 pb-24">
        <Bubble>안녕하세요! 다음 학기 시간표를 같이 짜볼게요.</Bubble>
        <Bubble delay={0.15}>
          먼저 지금까지 뭘 들었는지 알아야 해요.
          <br />
          <b>성적표를 그대로 붙여넣어 주세요.</b>
        </Bubble>

        {step === "transcript" && (
          <>
            <TranscriptInput busy={busy} onSubmit={handleTranscript} />
            {error && (
              <p role="alert" className="text-sm font-semibold text-danger">
                {error}
              </p>
            )}
          </>
        )}

        {step !== "transcript" && (
          <>
            <UserBubble>성적표 붙여넣기 완료</UserBubble>
            <Bubble delay={0.1}>
              읽었어요. 이렇게 인식했습니다.
              <RecognitionChips dept={deptLabel} year={2022} courses={courseCount} />
              어떤 일을 하고 싶으세요?
            </Bubble>
          </>
        )}

        {step === "job" && ref && <JobPicker jobs={ref.jobs} onPick={handleJob} />}

        {job && step !== "job" && (
          <>
            <UserBubble>{job.name}</UserBubble>
            <Bubble delay={0.1}>
              마지막이에요. 추천을 어느 쪽으로 기울일까요?
            </Bubble>
          </>
        )}

        {step === "mode" && ref && <ModePicker modes={ref.modes} onPick={handleMode} />}

        {mode && step === "done" && (
          <>
            <UserBubble>{mode.label}</UserBubble>
            <Bubble delay={0.1}>
              좋아요, 시간표를 짜볼게요…
              <span className="ml-2 inline-flex gap-1 align-middle">
                <Dot /> <Dot d={0.15} /> <Dot d={0.3} />
              </span>
            </Bubble>
          </>
        )}

        <div ref={endRef} />
      </div>
    </main>
  );
}

// ── 조각들 ─────────────────────────────────────────────────────

/**
 * 성적표에서 뽑아낸 것을 칩으로 띄운다.
 * 6월 프론트의 「토큰 비행」을 가볍게 옮긴 것 — 붙여넣은 글자가 그냥 사라지지 않고
 * 인식 결과로 바뀌었다는 걸 눈으로 잇는다. 순서대로 하나씩 떠오른다.
 */
function RecognitionChips({
  dept,
  year,
  courses,
}: {
  dept: string;
  year: number;
  courses: number;
}) {
  const chips = [dept, `${year}학번`, `${courses}과목`];
  return (
    <span className="my-2.5 flex flex-wrap gap-1.5">
      {chips.map((c, i) => (
        <span
          key={c}
          className="tnum rounded-sm bg-surface-3 px-2.5 py-1 text-caption font-semibold text-text"
          style={{ animation: `chipIn .45s cubic-bezier(.16,1,.3,1) ${0.12 * i}s both` }}
        >
          {c}
        </span>
      ))}
    </span>
  );
}

function Bubble({
  children,
  delay = 0,
}: {
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <div
      className="fade-up w-fit max-w-[85%] rounded-xl rounded-tl-sm bg-surface px-4 py-3 leading-relaxed shadow-card"
      style={{ animationDelay: `${delay}s` }}
    >
      {children}
    </div>
  );
}

function UserBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="fade-up ml-auto w-fit max-w-[85%] rounded-xl rounded-tr-sm bg-brand-600 px-4 py-3 text-white">
      {children}
    </div>
  );
}

function Dot({ d = 0 }: { d?: number }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 rounded-full bg-text-soft"
      style={{ animation: `fadeIn .6s ${d}s infinite alternate` }}
    />
  );
}

function StepDots({ step }: { step: Step }) {
  const order: Step[] = ["transcript", "job", "mode", "done"];
  const i = order.indexOf(step);
  return (
    <div className="flex gap-1.5">
      {order.map((s, idx) => (
        <span
          key={s}
          className="h-1.5 rounded-full transition-all duration-300"
          style={{
            width: idx === i ? "1.5rem" : "0.375rem",
            background: idx <= i ? "var(--color-brand-600)" : "var(--color-border-strong)",
          }}
        />
      ))}
    </div>
  );
}

function TranscriptInput({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (v: string) => void;
}) {
  const [value, setValue] = useState("");
  const found = countCourseLines(value);

  return (
    <div className="fade-up space-y-3" style={{ animationDelay: "0.3s" }}>
      <details open className="card overflow-hidden">
        <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-brand-700 hover:bg-surface-3">
          성적표 어디서 가져와요? ▾
        </summary>
        <ol className="space-y-2 border-t border-border px-4 py-3 text-sm text-text-muted">
          {[
            "클래스넷(cn.hongik.ac.kr) 로그인",
            "왼쪽 메뉴 → 성적정보 → 전체성적조회",
            "표 영역에서 Ctrl+A → Ctrl+C",
            "아래 칸에 Ctrl+V",
          ].map((s, i) => (
            <li key={i} className="flex gap-2.5">
              <span className="tnum mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-100 text-caption font-bold text-brand-700">
                {i + 1}
              </span>
              <span>{s}</span>
            </li>
          ))}
        </ol>
      </details>

      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={6}
        spellCheck={false}
        placeholder="여기에 붙여넣기 (Ctrl+V)"
        aria-describedby="paste-status"
        className="w-full resize-none rounded-lg border border-border bg-surface p-4 font-mono text-sm outline-none transition-colors placeholder:text-text-soft focus:border-brand-400"
      />

      {/* 붙여넣자마자 몇 과목 잡혔는지 알려준다. 제출 뒤에 알면 늦다. */}
      <p
        id="paste-status"
        aria-live="polite"
        className={
          "text-caption " +
          (value.trim() === ""
            ? "text-text-soft"
            : found > 0
              ? "text-success"
              : "text-gap")
        }
      >
        {value.trim() === ""
          ? "붙여넣으면 여기에 인식 결과가 뜹니다."
          : found > 0
            ? `✓ ${found}과목 인식했어요.`
            : "성적표 형식이 아닌 것 같아요. 표 전체를 Ctrl+A → Ctrl+C 로 복사했는지 확인해 주세요."}
      </p>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onSubmit(value)}
          disabled={found === 0 || busy}
          className="rounded-md bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-35"
        >
          {busy ? "읽는 중…" : "이걸로 할게요"}
        </button>
        <button
          onClick={() => {
            setValue(SAMPLE_TRANSCRIPT);
            onSubmit(SAMPLE_TRANSCRIPT);
          }}
          disabled={busy}
          className="rounded-md border border-border-strong px-5 py-2.5 text-sm font-semibold text-text-muted transition-colors hover:bg-surface-3"
        >
          샘플로 먼저 볼래요
        </button>
      </div>
    </div>
  );
}

/** 직무 아이콘 — 이모지는 기기마다 다르게 그려져서 직접 그린다. */
const JOB_ICON: Record<string, React.ReactNode> = {
  DA: <IconBars />,
  DS: <IconFlask />,
  DE: <IconPipe />,
  PM: <IconCompass />,
  MKT: <IconMegaphone />,
  FIN: <IconTrend />,
};

function JobPicker({
  jobs,
  onPick,
}: {
  jobs: JobRef[];
  onPick: (j: JobRef) => void;
}) {
  return (
    <div className="fade-up grid grid-cols-2 gap-2 sm:grid-cols-3">
      {[...jobs].sort((a, b) => jobRank(a.id) - jobRank(b.id)).map((j) => (
        <button
          key={j.id}
          onClick={() => onPick(j)}
          className="group flex flex-col items-center gap-2.5 rounded-lg border border-border bg-surface px-3 py-5 transition-colors hover:border-brand-400 hover:bg-brand-50"
        >
          <span className="text-text-soft transition-colors group-hover:text-brand-600">
            {JOB_ICON[j.id]}
          </span>
          <span className="text-sm font-semibold">{j.name}</span>
        </button>
      ))}
    </div>
  );
}

function ModePicker({
  modes,
  onPick,
}: {
  modes: ModeRef[];
  onPick: (m: ModeRef) => void;
}) {
  return (
    <div className="fade-up space-y-2">
      {modes.map((m) => (
        <button
          key={m.id}
          onClick={() => onPick(m)}
          className="w-full rounded-lg border border-border bg-surface px-4 py-3.5 text-left transition-colors hover:border-brand-400 hover:bg-brand-50"
        >
          <span className="block text-sm font-semibold">{m.label}</span>
          <span className="mt-0.5 block text-caption leading-snug text-text-muted">
            {m.desc}
          </span>
        </button>
      ))}
    </div>
  );
}

// ── 직무 아이콘 ─────────────────────────────────────────────────

const SVG = {
  width: 28,
  height: 28,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

function IconBars() {
  return (
    <svg {...SVG}>
      <path d="M4 20h16" />
      <rect x="5" y="12" width="3.5" height="5" rx=".7" />
      <rect x="10.25" y="8" width="3.5" height="9" rx=".7" />
      <rect x="15.5" y="4" width="3.5" height="13" rx=".7" />
    </svg>
  );
}

function IconFlask() {
  return (
    <svg {...SVG}>
      <path d="M9.5 3v6.2L4.6 17.4A2 2 0 0 0 6.3 20.5h11.4a2 2 0 0 0 1.7-3.1L14.5 9.2V3" />
      <path d="M8.4 3h7.2" />
      <path d="M6.9 14h10.2" />
    </svg>
  );
}

function IconPipe() {
  return (
    <svg {...SVG}>
      <ellipse cx="12" cy="5.5" rx="7" ry="2.6" />
      <path d="M5 5.5v13c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6v-13" />
      <path d="M5 12c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6" />
    </svg>
  );
}

function IconCompass() {
  return (
    <svg {...SVG}>
      <circle cx="12" cy="12" r="9" />
      <path d="M15.6 8.4 13.8 13.8 8.4 15.6 10.2 10.2z" />
    </svg>
  );
}

function IconMegaphone() {
  return (
    <svg {...SVG}>
      <path d="M3.5 10.5v3a1.5 1.5 0 0 0 1.5 1.5h2l7 4.5V6L7 10.5H5a1.5 1.5 0 0 0-1.5 1.5Z" />
      <path d="M17.5 9.2a4 4 0 0 1 0 5.6" />
      <path d="M6.5 15v4.5" />
    </svg>
  );
}

function IconTrend() {
  return (
    <svg {...SVG}>
      <path d="M4 19h16" />
      <path d="M5 15.5 10 10l3.2 3.2L19 6.5" />
      <path d="M15.2 6.5H19v3.8" />
    </svg>
  );
}
