"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { countCourseLines, fetchReference, submitTranscript } from "@/lib/api";
import { SAMPLE_TRANSCRIPTS } from "@/lib/sample";
import type { CreditLimit, JobRef, ModeRef, ProgramRef, Reference } from "@/lib/types";
import { jobRank } from "@/lib/competency";

type Step = "program" | "transcript" | "credits" | "job" | "mode" | "done";
/** 주소(`?step=`)로 오가는 단계. done 은 결과 화면으로 넘어가는 순간이라 기록에 안 올린다 */
const ORDER = ["program", "transcript", "credits", "job", "mode"] as const;

/** 신청 가능 최대학점으로 받을 수 있는 범위. 한 학기 최소 12학점(학사내규 제4조 ②), API 상한 30 */
const CREDIT_MIN = 12;
const CREDIT_MAX = 30;

/** 이 탭에 두는 답. 결과 화면에서 뒤로 오면 페이지가 새로 그려져서, 이게 없으면 처음부터 다시 묻는다 */
const FLOW_KEY = "startFlow";
interface Flow {
  dept: string | null;
  year: number | null;
  courseCount: number;
  estimate: CreditLimit | null;
  creditMax: number | null;
  jobId: string | null;
  modeId: string | null;
}
interface SavedTranscript {
  text: string;
  dept: string;
  admissionYear: number;
}

/** useSearchParams 를 쓰는 화면은 Suspense 안에 있어야 정적 빌드가 된다 */
export default function StartPage() {
  return (
    <Suspense>
      <StartFlow />
    </Suspense>
  );
}

/**
 * 성적표 입력 — 대화형.
 * 입력만 대화로 받고, 결과는 /result 에서 한 화면에 정적으로 보여준다.
 * 긴 폼 하나를 마주하는 것보다 세 번 물어보는 쪽이 이탈이 적다.
 */
function StartFlow() {
  const router = useRouter();
  const params = useSearchParams();
  const [ref, setRef] = useState<Reference | null>(null);
  const [dept, setDept] = useState<string | null>(null);
  const [year, setYear] = useState<number | null>(null);
  /** 마지막으로 서버에 넣은 성적표. 학과·학번이 그대로면 성적표 단계로 돌아왔을 때 칸을 채운다 */
  const [saved, setSaved] = useState<SavedTranscript | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [modeId, setModeId] = useState<string | null>(null);
  const [courseCount, setCourseCount] = useState(0);
  /** 성적표로 계산한 최대학점(서버). 입력 칸을 미리 채우는 데 쓴다 */
  const [estimate, setEstimate] = useState<CreditLimit | null>(null);
  /** 학생이 확인해 넣은 이번 학기 신청 가능 최대학점 */
  const [creditMax, setCreditMax] = useState<number | null>(null);
  /** 성향까지 골라 결과 화면으로 넘어가는 중 */
  const [submitting, setSubmitting] = useState(false);
  const [restored, setRestored] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const program = ref?.programs.find((p) => p.dept === dept) ?? null;
  const job = ref?.jobs.find((j) => j.id === jobId) ?? null;
  const mode = ref?.modes.find((m) => m.id === modeId) ?? null;
  const transcriptDone =
    saved !== null && saved.dept === dept && saved.admissionYear === year && courseCount > 0;

  // 지금 단계는 주소가 정한다. 뒤로 가기·앞으로 가기가 단계를 오가게 하려고 — 상태만 바꾸면
  // 브라우저 기록에 안 남아 뒤로 가기가 앞 질문이 아니라 랜딩으로 나갔다(#75).
  // 답이 없는 단계로 바로 들어오면(새로고침, 학과를 바꾼 뒤 앞으로 가기) 채울 수 있는 데까지만 간다.
  const ready = [true, program !== null && year !== null, transcriptDone, creditMax !== null, job !== null];
  const asked = Math.max(0, ORDER.indexOf(params.get("step") as (typeof ORDER)[number]));
  let at = 0;
  while (at < asked && ready[at + 1]) at++;
  const step: Step = submitting ? "done" : ORDER[at];
  /** 그 단계를 지나왔나 — 지나온 단계만 답 말풍선을 그린다 */
  const passed = (s: Step) => (submitting ? ORDER.length : at) > ORDER.indexOf(s as (typeof ORDER)[number]);

  function go(next: Step) {
    window.history.pushState(null, "", next === "program" ? "/start" : `/start?step=${next}`);
  }

  // 첫 렌더는 서버 렌더와 같아야 해서 저장해 둔 답은 마운트 뒤에 읽는다
  useEffect(() => {
    try {
      const f = JSON.parse(sessionStorage.getItem(FLOW_KEY) ?? "null") as Flow | null;
      if (f) {
        setDept(f.dept);
        setYear(f.year);
        setCourseCount(f.courseCount);
        setEstimate(f.estimate);
        setCreditMax(f.creditMax);
        setJobId(f.jobId);
        setModeId(f.modeId);
      }
      setSaved(JSON.parse(sessionStorage.getItem("transcript") ?? "null"));
    } catch {
      // 깨진 값이면 처음부터 묻는다
    }
    setRestored(true);
  }, []);

  useEffect(() => {
    if (!restored) return;
    const f: Flow = { dept, year, courseCount, estimate, creditMax, jobId, modeId };
    sessionStorage.setItem(FLOW_KEY, JSON.stringify(f));
  }, [restored, dept, year, courseCount, estimate, creditMax, jobId, modeId]);

  // 실패를 삼키면 화면이 그냥 비어 버린다 — 사용자는 뭘 눌러야 할지도 모른 채 멈춘다.
  // (CORS 차단은 서버에 200으로 기록되기까지 해서, 화면에 안 띄우면 원인을 찾을 수 없다.)
  useEffect(() => {
    fetchReference()
      .then(setRef)
      .catch((e) => {
        console.error(e);
        setError("서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.");
      });
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [step]);

  async function handleTranscript(value: string) {
    if (!value.trim() || busy || !program || year === null) return;
    setBusy(true);
    setError(null);
    try {
      const res = await submitTranscript({
        text: value,
        dept: program.dept,
        admissionYear: year,
      });
      sessionStorage.setItem("studentId", res.studentId);
      // 샘플로 들어왔으면 결과 화면이 「샘플 학생의 결과」라고 밝힌다 — 안 그러면 적합도를 제 것으로 읽는다
      if (value === SAMPLE_TRANSCRIPTS[program.dept]?.[year]) sessionStorage.setItem("sample", "1");
      else sessionStorage.removeItem("sample");
      // 서버는 잠들거나 재시작하면 적재한 성적표를 잃는다(무료 인스턴스의 임시 파일시스템).
      // 결과 화면이 그때 다시 적재할 수 있게 이 탭에만 둔다 — 탭을 닫으면 사라진다.
      const t: SavedTranscript = { text: value, dept: program.dept, admissionYear: year };
      sessionStorage.setItem("transcript", JSON.stringify(t));
      // 결과 화면의 학점 선택지 상한. 이전 성적표의 값이 남지 않게 없으면 지운다
      if (res.creditLimit) sessionStorage.setItem("creditLimit", JSON.stringify(res.creditLimit));
      else sessionStorage.removeItem("creditLimit");
      sessionStorage.removeItem("creditMax");
      setEstimate(res.creditLimit ?? null);
      setCourseCount(res.courseCount);
      setCreditMax(null);
      setSaved(t);
      go("credits");
    } catch (e) {
      console.error(e);
      setError("성적표를 읽는 중 문제가 생겼어요. 잠시 후 다시 눌러주세요.");
    } finally {
      setBusy(false);
    }
  }

  function handleCredits(n: number) {
    sessionStorage.setItem("creditMax", String(n));
    setCreditMax(n);
    go("job");
  }

  function handleJob(j: JobRef) {
    setJobId(j.id);
    go("mode");
  }

  function handleMode(m: ModeRef) {
    setModeId(m.id);
    setSubmitting(true);
    setTimeout(() => {
      router.push(`/result?job=${job!.id}&mode=${m.id}`);
    }, 900);
  }

  return (
    // relative: 안의 sr-only(absolute)가 위치 기준을 못 찾으면
    // 초기 컨테이닝 블록에 놓여 문서 폭이 늘어난다.
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
          졸업요건은 학과와 입학년도마다 달라요.
          <br />
          <b>어느 학과 몇 학번이세요?</b>
        </Bubble>

        {step === "program" && error && (
          <p role="alert" className="text-sm font-semibold text-danger">
            {error}
          </p>
        )}

        {/* 참조 데이터를 기다리는 동안 버튼 자리가 통째로 비어 화면이 멈춘 것처럼 보였다.
            무료 호스팅 콜드스타트라 20~30초까지 가므로, 기다리는 중이라고 말해 준다. */}
        {step === "program" && !ref && !error && <WaitingForServer />}

        {step === "program" && ref && (
          <ProgramPicker
            programs={ref.programs}
            picked={program}
            onPickProgram={(p) => {
              setDept(p.dept);
              setYear(null);
            }}
            onPickYear={(y) => {
              setYear(y);
              go("transcript");
            }}
          />
        )}

        {passed("program") && program && year !== null && (
          <>
            <UserBubble>
              {program.name} {year}학번
            </UserBubble>
            <Bubble delay={0.1}>
              이제 지금까지 뭘 들었는지 알아야 해요.
              <br />
              <b>성적표를 그대로 붙여넣어 주세요.</b>
            </Bubble>
          </>
        )}

        {step === "transcript" && (
          <>
            <TranscriptInput
              busy={busy}
              onSubmit={handleTranscript}
              // 돌아왔으면 넣었던 성적표를 채워 둔다. 샘플이었으면 비운다 — 이번엔 제 것을 넣으러 온 것이다
              initial={transcriptDone && sessionStorage.getItem("sample") !== "1" ? saved!.text : ""}
              sample={program && year !== null ? (SAMPLE_TRANSCRIPTS[program.dept]?.[year] ?? null) : null}
            />
            {error && (
              <p role="alert" className="text-sm font-semibold text-danger">
                {error}
              </p>
            )}
          </>
        )}

        {passed("transcript") && program && year !== null && (
          <>
            <UserBubble>성적표 붙여넣기 완료</UserBubble>
            <Bubble delay={0.1}>
              읽었어요. 이렇게 인식했습니다.
              <RecognitionChips dept={program.name} year={year} courses={courseCount} />
              <b>이번 학기에 몇 학점까지 신청할 수 있어요?</b>
            </Bubble>
          </>
        )}

        {step === "credits" && (
          <CreditsInput estimate={estimate} initial={creditMax} onPick={handleCredits} />
        )}

        {passed("credits") && creditMax !== null && (
          <>
            <UserBubble>최대 {creditMax}학점</UserBubble>
            <Bubble delay={0.1}>어떤 일을 하고 싶으세요?</Bubble>
          </>
        )}

        {step === "job" && ref && <JobPicker jobs={ref.jobs} onPick={handleJob} />}

        {passed("job") && job && (
          <>
            <UserBubble>{job.name}</UserBubble>
            <Bubble delay={0.1}>
              마지막이에요. 추천을 어느 쪽으로 기울일까요?
            </Bubble>
          </>
        )}

        {step === "mode" && ref && <ModePicker modes={ref.modes} onPick={handleMode} />}

        {submitting && mode && (
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

/**
 * 참조 데이터를 기다리는 동안 보여 줄 자리.
 *
 * 그냥 비워 두면 「버튼이 안 뜬다」가 아니라 「고장났다」로 읽힌다.
 * 첫 호출이 오래 걸릴 수 있다는 사실까지 적어야 기다릴 마음이 생긴다.
 */
function WaitingForServer() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="fade-up flex w-fit items-center gap-2.5 rounded-xl rounded-tl-sm bg-surface-3 px-4 py-3 text-sm text-text-muted"
    >
      <span className="flex gap-1" aria-hidden>
        <Dot />
        <Dot d={0.2} />
        <Dot d={0.4} />
      </span>
      학과 목록을 불러오는 중이에요. 한동안 아무도 안 쓰면 서버가 잠들어서, 깨는 데 1분쯤 걸려요.
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
  const order: Step[] = ["program", "transcript", "credits", "job", "mode", "done"];
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

/**
 * 이번 학기 신청 가능 최대학점. 학생마다 다르다(직전학기 평점 우수 +3, 남은 학점 이월 최대 +2).
 * 정답은 클래스넷에 있어 거기서 보고 넣게 한다. 성적표로 계산한 값을 미리 채워 두어
 * 대부분은 확인만 하고 넘어가고, 다르면 고친다.
 */
function CreditsInput({
  estimate,
  initial,
  onPick,
}: {
  estimate: CreditLimit | null;
  /** 이미 넣었던 값(뒤로 돌아온 경우) */
  initial: number | null;
  onPick: (n: number) => void;
}) {
  const [raw, setRaw] = useState(String(initial ?? estimate?.max ?? 18));
  const n = Number(raw);
  const valid = raw.trim() !== "" && Number.isInteger(n) && n >= CREDIT_MIN && n <= CREDIT_MAX;
  const step = (d: number) =>
    setRaw(String(Math.min(CREDIT_MAX, Math.max(CREDIT_MIN, (valid ? n : estimate?.max ?? 18) + d))));

  return (
    <div className="fade-up space-y-3" style={{ animationDelay: "0.3s" }}>
      <p className="text-sm text-text-muted">
        클래스넷 → 수강신청 → <b className="text-text">개인별 수강가능학점 조회</b>의
        「금학기 신청가능 최대학점」이에요.
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => step(-1)}
          aria-label="1학점 줄이기"
          className="min-h-11 w-11 rounded-md border border-border-strong text-lg font-semibold text-text-muted hover:bg-surface-3"
        >
          −
        </button>
        <input
          type="number"
          inputMode="numeric"
          min={CREDIT_MIN}
          max={CREDIT_MAX}
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          aria-label="이번 학기 신청 가능 최대학점"
          aria-describedby="credits-hint"
          className="tnum min-h-11 w-20 rounded-md border border-border bg-surface text-center text-base font-semibold outline-none focus:border-brand-400"
        />
        <button
          type="button"
          onClick={() => step(1)}
          aria-label="1학점 늘리기"
          className="min-h-11 w-11 rounded-md border border-border-strong text-lg font-semibold text-text-muted hover:bg-surface-3"
        >
          +
        </button>
        <span className="text-sm text-text-muted">학점</span>
      </div>
      <p id="credits-hint" className={"text-caption " + (valid ? "text-text-soft" : "text-gap")}>
        {!valid
          ? `${CREDIT_MIN}~${CREDIT_MAX} 사이의 수로 넣어 주세요.`
          : estimate
            ? `성적표로 계산하면 ${estimate.max}학점이에요 (이수한계 ${estimate.base}` +
              (estimate.gpaBonus ? ` + 평점 우수 ${estimate.gpaBonus}` : "") +
              (estimate.carry ? ` + 이월 ${estimate.carry}` : "") +
              "). 클래스넷 값과 다르면 고쳐 주세요."
            : "모르겠으면 18 그대로 두셔도 돼요."}
      </p>
      <button
        onClick={() => onPick(n)}
        disabled={!valid}
        className="rounded-md bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-35"
      >
        {valid ? `${n}학점으로 할게요` : "학점을 넣어 주세요"}
      </button>
    </div>
  );
}

function TranscriptInput({
  busy,
  onSubmit,
  sample,
  initial,
}: {
  busy: boolean;
  onSubmit: (v: string) => void;
  /** 고른 학과의 샘플. 학과가 다른 샘플을 넣으면 학번·학년·과목이 어긋나서 없으면 버튼을 숨긴다(#41) */
  sample: string | null;
  initial: string;
}) {
  const [value, setValue] = useState(initial);
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
            "표 영역에서 Ctrl+A → Ctrl+C (휴대폰은 길게 눌러 전체 선택 → 복사)",
            "아래 칸에 Ctrl+V (휴대폰은 길게 눌러 붙여넣기)",
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
        placeholder="여기에 붙여넣기"
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
            : "성적표 형식이 아닌 것 같아요. 전체성적조회 화면 전체를 선택해 복사했는지 확인해 주세요."}
      </p>
      {/* 화면 일부만 복사하면 과목 몇 개만 잡히고도 그대로 넘어간다. 전체성적조회는 맨 아래에
          「총 취득학점」 줄이 있어 그게 없으면 잘렸다고 알린다 — 막지는 않는다 */}
      {found > 0 && !/총\s*취득학점/.test(value) && (
        <p className="text-caption text-gap">
          맨 아래 「총 취득학점」 줄이 안 보여요. 성적표 끝까지 복사됐는지 확인해 주세요.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onSubmit(value)}
          disabled={found === 0 || busy}
          className="rounded-md bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-35"
        >
          {busy ? "읽는 중…" : "이걸로 할게요"}
        </button>
        {sample !== null && (
          <button
            onClick={() => {
              setValue(sample);
              onSubmit(sample);
            }}
            disabled={busy}
            className="rounded-md border border-border-strong px-5 py-2.5 text-sm font-semibold text-text-muted transition-colors hover:bg-surface-3"
          >
            샘플로 먼저 볼래요
          </button>
        )}
      </div>

      {/* 결정 ⑧ — 구조가 이러하므로 사실인 문장만 쓴다. 학번·이름은 '전체성적조회'
          화면에 없어 파서가 가져올 수조차 없고, 적재분은 24시간 뒤 삭제된다. 서버가 잠들어 잃었을
          때 다시 적재하려고 이 탭에도 둔다(#69) — 그것까지 적는다. */}
      <p className="text-caption leading-relaxed text-text-soft">
        붙여넣은 성적표는 추천 계산에만 쓰이고 서버에서 <b>24시간 후 자동 삭제</b>됩니다.
        이 브라우저 탭에도 잠시 남았다가 탭을 닫으면 지워집니다.
        로그인이 없어 학번·이름은 수집하지 않습니다.
      </p>
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

/**
 * 학과 · 입학년도 선택.
 *
 * 고를 수 있는 연도는 `fromYear ~ 올해` 다. fromYear 는 교육과정 **개정 연도**라
 * 그 이후 학번은 모두 같은 요건을 따른다(경영 2022 과정 = 22~26학번).
 * 지원하지 않는 조합은 애초에 화면에 없으므로 사용자가 에러를 만날 일이 없다.
 */
function ProgramPicker({
  programs,
  picked,
  onPickProgram,
  onPickYear,
}: {
  programs: ProgramRef[];
  picked: ProgramRef | null;
  onPickProgram: (p: ProgramRef) => void;
  onPickYear: (y: number) => void;
}) {
  const thisYear = new Date().getFullYear();
  const years = picked
    ? Array.from(
        { length: Math.max(1, thisYear - picked.fromYear + 1) },
        (_, i) => picked.fromYear + i,
      )
    : [];

  return (
    <div className="fade-up space-y-4">
      <div className="grid grid-cols-2 gap-2">
        {programs.map((p) => {
          const on = picked?.dept === p.dept;
          return (
            <button
              key={p.dept}
              onClick={() => onPickProgram(p)}
              aria-pressed={on}
              className={`rounded-lg border px-3 py-4 text-sm font-semibold transition-colors ${
                on
                  ? "border-brand-400 bg-brand-50 text-brand-700"
                  : "border-border bg-surface hover:border-brand-400 hover:bg-brand-50"
              }`}
            >
              {p.name}
            </button>
          );
        })}
      </div>

      {picked && (
        <div className="fade-up space-y-2">
          <p className="text-sm text-text-muted">몇 학번이세요?</p>
          <div className="flex flex-wrap gap-2">
            {years.map((y) => (
              <button
                key={y}
                onClick={() => onPickYear(y)}
                className="tnum min-h-11 rounded-lg border border-border bg-surface px-4 text-sm font-semibold transition-colors hover:border-brand-400 hover:bg-brand-50"
              >
                {y}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

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
