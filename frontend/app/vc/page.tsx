"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  AnimatePresence,
  motion,
  MotionConfig,
  useReducedMotion,
} from "motion/react";
import { Sparkles, ChevronDown } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { JobCard } from "@/components/domain/job-card";
import { JobToggleBar } from "@/components/domain/job-toggle-bar";
import { FitScore } from "@/components/domain/fit-score";
import { MaskReveal } from "@/components/domain/mask-reveal";
import { CountUp } from "@/components/domain/count-up";
import { CourseRow } from "@/components/domain/course-row";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  JOBS,
  JOB_PLANS,
  RECOGNITION,
  UNSURE_HINT,
  planSummary,
  type JobId,
} from "@/lib/data";
import { EASE, SPRING } from "@/lib/motion";
import { GhostTimetable } from "./ghost-timetable";
import { AssemblyGrid } from "./assembly-grid";

type RecogState = "idle" | "parsing" | "recognized";

// 자가 타이핑 유령 placeholder: 현실적인 성적표 1~2줄 (digits + uppercase).
const GHOST_LINES = [
  "2024-2  데이터구조  A0  3.0",
  "2024-1  운영체제  B+  3.0",
];
const TYPE_MS = 55;
const HOLD_MS = 1400;
const BACKSPACE_MS = 28;

function useMounted() {
  // 클라이언트 마운트 감지 (setState-in-effect 없이 lint-safe).
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

export default function VcPage() {
  return (
    <MotionConfig reducedMotion="user">
      <VcFlow />
    </MotionConfig>
  );
}

function VcFlow() {
  const [transcript, setTranscript] = useState("");
  const [recog, setRecog] = useState<RecogState>("idle");
  const [selectedJob, setSelectedJob] = useState<JobId | null>(null);
  const [unsureOpen, setUnsureOpen] = useState(false);
  const [highlightJobs, setHighlightJobs] = useState<readonly JobId[] | null>(
    null,
  );
  const [activeCourse, setActiveCourse] = useState<string | null>(null);
  // 첫 결과 조립 여부 (직무 전환 시 false → glide/crossfade).
  const [firstAssembly, setFirstAssembly] = useState(true);
  // 입력 필드 포커스 여부 (유령은 포커스 순간 완전히 사라진다).
  const [fieldFocused, setFieldFocused] = useState(false);

  const resultRef = useRef<HTMLDivElement | null>(null);
  const jobsRef = useRef<HTMLDivElement | null>(null);

  const hasText = transcript.trim().length > 0;
  // 유령은 입력 전 + 포커스 전에만 살아 있다. 포커스/입력 순간 완전히 죽는다.
  const ghostActive = recog === "idle" && !hasText && !fieldFocused;

  // paste/입력 → parsing → recognized (mock: 글자 있으면 인식). 비동기 콜백에서만 전이.
  useEffect(() => {
    if (!hasText) return;
    const t = setTimeout(() => setRecog("recognized"), 620);
    return () => clearTimeout(t);
  }, [hasText]);

  // 인식되면 직무 영역으로 부드럽게 안내 (외부 시스템 = 스크롤).
  const recognized = recog === "recognized";
  useEffect(() => {
    if (recognized && !selectedJob) {
      const t = setTimeout(
        () =>
          jobsRef.current?.scrollIntoView({
            behavior: "smooth",
            block: "nearest",
          }),
        360,
      );
      return () => clearTimeout(t);
    }
  }, [recognized, selectedJob]);

  useEffect(() => {
    if (!selectedJob) return;
    const t = setTimeout(
      () =>
        resultRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        }),
      120,
    );
    return () => clearTimeout(t);
  }, [selectedJob]);

  function handleTranscriptChange(value: string) {
    setTranscript(value);
    setRecog(value.trim().length > 0 ? "parsing" : "idle");
  }

  function handleSelectJob(id: JobId) {
    setActiveCourse(null);
    setHighlightJobs(null);
    // 이미 결과가 있으면(직무 전환) 조립 애니메이션을 끈다.
    setFirstAssembly((prev) => (selectedJob ? false : prev));
    setSelectedJob(id);
  }

  const summary = useMemo(
    () => (selectedJob ? planSummary(selectedJob) : null),
    [selectedJob],
  );
  const plan = selectedJob ? JOB_PLANS[selectedJob] : null;
  const activeCourseData = useMemo(() => {
    if (!plan || !activeCourse) return null;
    return plan.courses.find((c) => c.id === activeCourse) ?? null;
  }, [plan, activeCourse]);

  return (
    <div className="relative flex min-h-dvh flex-col">
      {/* warm blueprint 배경 (가장자리 페이드) */}
      <div
        aria-hidden
        className="bg-blueprint pointer-events-none fixed inset-0 -z-10 [mask-image:radial-gradient(ellipse_at_top,black,transparent_72%)]"
      />
      <SiteHeader />

      <main className="mx-auto w-full max-w-[1080px] flex-1 px-6 pt-12 pb-28">
        {/* ── 히어로 ────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: EASE }}
          className="max-w-2xl"
        >
          <h1 className="text-[2.6rem] leading-[1.1] font-bold tracking-[-0.03em] break-keep text-balance">
            목표 직무에 맞는
            <br className="hidden sm:block" /> 다음 학기 시간표.
          </h1>
          <p className="text-ink-muted mt-3 text-[1.02rem] tracking-[-0.01em]">
            성적표만 붙여넣으면 돼요.
          </p>
        </motion.div>

        {/* ── ① 성적표 paste (뒤에 유령 시간표 자가시연) ───────── */}
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.06, ease: EASE }}
          aria-labelledby="paste-heading"
          className="relative mt-7"
        >
          <h2 id="paste-heading" className="sr-only">
            성적표 붙여넣기
          </h2>

          {/* 유령 시간표 레이어: 카드 뒤, 동일 격자 기하 → CLS 0. */}
          <div
            aria-hidden
            className="absolute inset-x-0 top-0 -z-10 px-4 pt-16"
          >
            <GhostTimetable active={ghostActive} />
          </div>

          <Card className="bg-surface/85 relative backdrop-blur-sm">
            <CardContent className="space-y-3 p-4">
              <PasteField
                value={transcript}
                recognized={recognized}
                recog={recog}
                focused={fieldFocused}
                onFocusChange={setFieldFocused}
                onChange={handleTranscriptChange}
              />

              {/* 인식 상태: parsing → recognized (idle은 비워 둔다) */}
              <div id="recog-status" className="flex min-h-8 items-center">
                <AnimatePresence mode="wait" initial={false}>
                  {recog === "parsing" && (
                    <motion.div
                      key="parsing"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="text-ink-muted flex items-center gap-2 text-[0.82rem]"
                    >
                      <span className="border-line border-t-accent size-3.5 animate-spin rounded-full border-2" />
                      성적표를 읽는 중
                    </motion.div>
                  )}
                  {recog === "recognized" && (
                    <motion.div
                      key="recognized"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.3, ease: EASE }}
                      className="flex flex-wrap items-center gap-1.5"
                    >
                      <RecogChip label={RECOGNITION.department} delay={0} />
                      <RecogChip
                        label={RECOGNITION.admissionYear}
                        numeric
                        delay={0.06}
                      />
                      <RecogChip
                        count={RECOGNITION.earnedCredits}
                        suffix="학점"
                        delay={0.12}
                      />
                      <RecogChip
                        count={RECOGNITION.gpa}
                        decimals={1}
                        prefix="GPA "
                        delay={0.18}
                      />
                      <RecogChip
                        count={RECOGNITION.recognizedCourses}
                        suffix="과목 인식"
                        accent
                        delay={0.34}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* 프라이버시: 상태와 무관하게 상주하는 신뢰 신호 */}
              <p className="text-ink-subtle text-[0.8rem]">
                로그인 정보는 받지 않고, 붙여넣은 텍스트는 학점 계산에만 쓰고
                저장하지 않아요
              </p>
            </CardContent>
          </Card>
        </motion.section>

        {/* ── ② 직무 선택 (인식 후 공개) ──────────────────────── */}
        <div ref={jobsRef} className="scroll-mt-28">
          <AnimatePresence>
            {recognized && (
              <motion.section
                key="jobs"
                aria-labelledby="job-heading"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={SPRING.smooth}
                className="mt-10"
              >
                <div className="mb-4 flex items-baseline justify-between gap-3">
                  <h2
                    id="job-heading"
                    className="text-[0.95rem] font-semibold tracking-tight"
                  >
                    어떤 직무를 목표로 하나요?
                  </h2>
                  <span className="text-ink-subtle text-[0.78rem]">
                    하나 선택
                  </span>
                </div>

                <div
                  role="radiogroup"
                  aria-label="목표 직무"
                  className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3"
                >
                  {JOBS.map((job, i) => (
                    <JobCard
                      key={job.id}
                      job={job}
                      index={i}
                      selected={selectedJob === job.id}
                      dimmed={
                        highlightJobs ? !highlightJobs.includes(job.id) : false
                      }
                      onSelect={handleSelectJob}
                    />
                  ))}
                </div>

                {/* 잘 모르겠어요: 자동 선택 금지, 힌트만 */}
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={() => setUnsureOpen((v) => !v)}
                    aria-expanded={unsureOpen}
                    className="text-ink-muted hover:text-ink inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] text-[0.85rem] font-medium transition-colors outline-none focus-visible:ring-focus"
                  >
                    <Sparkles className="size-3.5" />
                    잘 모르겠어요
                    <ChevronDown
                      className={
                        unsureOpen
                          ? "size-3.5 rotate-180 transition-transform"
                          : "size-3.5 transition-transform"
                      }
                      aria-hidden
                    />
                  </button>
                  <AnimatePresence initial={false}>
                    {unsureOpen && (
                      <motion.div
                        key="unsure"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.32, ease: EASE }}
                        className="overflow-hidden"
                      >
                        <div className="border-accent/35 bg-accent-wash mt-2.5 rounded-[var(--radius)] border p-4">
                          <p className="text-ink text-[0.88rem] leading-relaxed">
                            {UNSURE_HINT.lead}
                          </p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {UNSURE_HINT.buckets.map((b) => (
                              <button
                                key={b.label}
                                type="button"
                                onClick={() => {
                                  // 자동 선택은 안 한다 (확정 흐름). 방향 카드만 강조.
                                  setHighlightJobs(b.jobs);
                                  setUnsureOpen(false);
                                  jobsRef.current?.scrollIntoView({
                                    behavior: "smooth",
                                    block: "start",
                                  });
                                }}
                                className="border-accent/40 bg-surface text-accent-strong hover:border-accent rounded-[var(--radius-sm)] border px-3 py-1.5 text-[0.82rem] font-medium transition-colors outline-none focus-visible:ring-focus"
                              >
                                {b.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </motion.section>
            )}
          </AnimatePresence>
        </div>

        {/* ── ③ 결과: THE ASSEMBLY ──────────────────────────────── */}
        <div ref={resultRef} className="scroll-mt-20">
          <AnimatePresence>
            {selectedJob && summary && plan && (
              <motion.section
                key="result-shell"
                aria-label="추천 시간표"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.5, ease: EASE }}
                className="mt-12"
              >
                {/* 직무 토글 바 (switch and see) */}
                <JobToggleBar active={selectedJob} onChange={handleSelectJob} />

                {/* 한 줄 요약: job-name MaskReveal (act 1) */}
                <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
                  <h2 className="text-[1.55rem] font-semibold tracking-[-0.02em]">
                    <span className="text-accent-strong">
                      {/* job key 로 re-mask: 직무 바뀌면 다시 올라온다 */}
                      <MaskReveal key={selectedJob}>{summary.jobName}</MaskReveal>
                    </span>{" "}
                    맞춤 시간표
                  </h2>
                  <Badge variant="accent">충돌 {summary.conflicts}건</Badge>
                  <span className="text-ink-muted inline-flex items-baseline gap-1.5 text-[0.9rem]">
                    적합도
                    <FitScore
                      value={summary.fitScore}
                      className="text-accent-strong text-[1.05rem] font-semibold"
                    />
                    <span className="text-ink-subtle font-mono text-[0.8rem] tabular-nums">
                      / 100
                    </span>
                  </span>
                  <span className="text-ink-subtle font-mono text-[0.8rem] tabular-nums">
                    {summary.courseCount}과목 / {summary.totalCredits}학점
                  </span>
                </div>

                {/* rationale: MaskReveal up (act 3) — job key 로 re-mask */}
                <p className="text-ink-muted mt-1.5 max-w-2xl text-[0.9rem] leading-relaxed break-keep">
                  <MaskReveal key={selectedJob} delay={0.12}>
                    {summary.rationale}
                  </MaskReveal>
                </p>

                {/* 조립 격자 + 과목 리스트 */}
                <div className="mt-4 grid gap-4 lg:grid-cols-[1.65fr_1fr]">
                  <Card>
                    <CardContent className="p-4">
                      <AssemblyGrid
                        jobKey={selectedJob}
                        courses={plan.courses}
                        selectedCourseId={activeCourse}
                        firstAssembly={firstAssembly}
                        onSelectCourse={(id) =>
                          setActiveCourse((cur) => (cur === id ? null : id))
                        }
                      />

                      {/* 과목 탭 시: 역량 1줄 + 근사 반사실 1줄 */}
                      <AnimatePresence initial={false}>
                        {activeCourseData && (
                          <motion.div
                            key={activeCourseData.id}
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.3, ease: EASE }}
                            className="overflow-hidden"
                          >
                            <div className="border-accent/35 bg-accent-wash mt-3 rounded-[var(--radius-sm)] border p-3">
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-accent-strong text-[0.88rem] font-semibold">
                                  {activeCourseData.name}
                                </span>
                                <span className="text-ink-muted font-mono text-[0.72rem] tabular-nums">
                                  {activeCourseData.slotLabel}
                                </span>
                              </div>
                              <p className="text-ink mt-1.5 text-[0.84rem] leading-relaxed">
                                <span className="text-ink-muted">
                                  기르는 역량
                                </span>{" "}
                                {activeCourseData.competency}
                              </p>
                              <p className="text-ink-muted mt-1 text-[0.82rem]">
                                <span className="text-ink-muted">
                                  빼면 적합도
                                </span>{" "}
                                <span className="text-accent-strong font-mono font-medium tabular-nums">
                                  {Math.abs(activeCourseData.counterfactual)}pt↓
                                </span>
                              </p>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <span className="text-[0.9rem] font-semibold tracking-tight">
                          추천 과목
                        </span>
                      </div>
                      <ul className="space-y-2">
                        {plan.courses.map((course, i) => (
                          <CourseRow
                            key={`${selectedJob}-${course.id}`}
                            course={course}
                            index={i}
                          />
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                </div>
              </motion.section>
            )}
          </AnimatePresence>
        </div>

        <p className="text-ink-subtle mt-16 text-center text-[0.72rem]">
          예시 데이터로 만든 발표 데모입니다
        </p>
      </main>
    </div>
  );
}

/* ──────────────────────────── 보조 컴포넌트 ─────────────────────── */

/**
 * 성적표 입력 필드 + 자가 타이핑 유령 placeholder + parsing 스캔라인.
 * 유령 타이핑은 비어 있고 포커스 안 됐을 때만 돈다. 포커스/입력 순간 죽는다.
 */
function PasteField({
  value,
  recognized,
  recog,
  focused,
  onFocusChange,
  onChange,
}: {
  value: string;
  recognized: boolean;
  recog: RecogState;
  focused: boolean;
  onFocusChange: (focused: boolean) => void;
  onChange: (value: string) => void;
}) {
  const reduce = useReducedMotion();
  const mounted = useMounted();
  const [typed, setTyped] = useState("");

  const hasValue = value.length > 0;
  // 유령 타이핑 active: 마운트됨 + 빈 값 + 포커스 안 됨 + reduced 아님.
  const typingActive = mounted && !focused && !hasValue && !reduce;

  const lineRef = useRef(0);
  const phaseRef = useRef<"typing" | "holding" | "deleting">("typing");
  const charRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 자가 타이핑 루프: setTimeout 체인 (effect 본문에서 동기 setState 안 함).
  useEffect(() => {
    if (!typingActive) {
      // 멈출 때 타이핑 텍스트도 리셋되도록 콜백으로 비운다.
      timerRef.current = setTimeout(() => setTyped(""), 0);
      return () => {
        if (timerRef.current) clearTimeout(timerRef.current);
      };
    }

    let cancelled = false;
    function step() {
      if (cancelled) return;
      const line = GHOST_LINES[lineRef.current % GHOST_LINES.length];
      const phase = phaseRef.current;

      if (phase === "typing") {
        charRef.current += 1;
        setTyped(line.slice(0, charRef.current));
        if (charRef.current >= line.length) {
          phaseRef.current = "holding";
          timerRef.current = setTimeout(step, HOLD_MS);
        } else {
          timerRef.current = setTimeout(step, TYPE_MS);
        }
      } else if (phase === "holding") {
        phaseRef.current = "deleting";
        timerRef.current = setTimeout(step, BACKSPACE_MS);
      } else {
        charRef.current -= 1;
        setTyped(line.slice(0, Math.max(0, charRef.current)));
        if (charRef.current <= 0) {
          phaseRef.current = "typing";
          lineRef.current += 1;
          timerRef.current = setTimeout(step, TYPE_MS * 4);
        } else {
          timerRef.current = setTimeout(step, BACKSPACE_MS);
        }
      }
    }

    timerRef.current = setTimeout(step, TYPE_MS * 6);
    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [typingActive]);

  // placeholder: 타이핑 중이면 자가 타이핑 텍스트(+커서), 아니면 정적 안내.
  const placeholder = typingActive
    ? `${typed}█`
    : "복사한 성적표를 여기에 붙여넣기";

  return (
    <div className="relative">
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => onFocusChange(true)}
        onBlur={() => onFocusChange(false)}
        placeholder={placeholder}
        className={
          recognized
            ? "border-accent min-h-44 border-solid"
            : "border-line-strong min-h-44 border-2 border-dashed transition-[border-style]"
        }
        aria-describedby="recog-status"
      />

      {/* parsing 스캔라인: 2px 그린이 top→bottom 1회 sweep 후 unmount. */}
      <AnimatePresence>
        {recog === "parsing" && !reduce && (
          <motion.span
            key="scanline"
            aria-hidden
            className="bg-accent pointer-events-none absolute inset-x-0 top-0 h-[2px] origin-top"
            initial={{ top: "0%", opacity: 0.9 }}
            animate={{ top: "100%", opacity: 0.9 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.0, ease: EASE }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * 인식 칩. count 가 있으면 CountUp 으로 0에서 굴러 올라온다 (숫자 칩 전용).
 * 그린은 accent 칩(24과목 인식) 하나에만 예약.
 */
function RecogChip({
  label,
  count,
  decimals = 0,
  prefix = "",
  suffix = "",
  numeric,
  accent,
  delay = 0,
}: {
  label?: string;
  count?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  numeric?: boolean;
  accent?: boolean;
  delay?: number;
}) {
  return (
    <motion.span
      initial={{ opacity: 0, y: 4, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.34, delay, ease: EASE }}
      className={
        accent
          ? "border-accent/40 bg-accent-wash text-accent-strong inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] border px-2.5 py-1 text-[0.78rem] font-medium"
          : "border-line bg-surface-muted text-ink-muted inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] border px-2.5 py-1 text-[0.78rem] font-medium"
      }
    >
      {accent && <span className="bg-accent-strong size-1.5 rounded-full" />}
      {count !== undefined ? (
        <CountUp
          value={count}
          decimals={decimals}
          prefix={prefix}
          suffix={suffix}
          className="text-[0.78rem]"
        />
      ) : (
        <span className={numeric ? "font-mono tabular-nums" : undefined}>
          {label}
        </span>
      )}
    </motion.span>
  );
}
