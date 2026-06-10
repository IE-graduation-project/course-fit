"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AnimatePresence,
  MotionConfig,
  motion,
  useReducedMotion,
} from "motion/react";
import { ChevronDown, Sparkles } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { MorphJobCard } from "./morph-job-card";
import { MorphGrid } from "./morph-grid";
import { JobToggleBar } from "@/components/domain/job-toggle-bar";
import { FitScore } from "@/components/domain/fit-score";
import { CompetencyChart } from "@/components/domain/competency-chart";
import { CompetencyBars } from "@/components/domain/competency-bars";
import { CourseRow } from "@/components/domain/course-row";
import { CountUp } from "@/components/domain/count-up";
import { MaskReveal } from "@/components/domain/mask-reveal";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import {
  CREDIT_RANGE,
  DEFAULT_CREDITS,
  JOBS,
  JOB_COMPETENCIES,
  JOB_INSIGHT,
  JOB_PLANS,
  RECOGNITION,
  UNSURE_HINT,
  planSummary,
  type JobId,
} from "@/lib/data";
import { EASE, SPRING } from "@/lib/motion";

type RecogState = "idle" | "parsing" | "recognized";

type Token = {
  k: string;
  label: string;
  kind: "text" | "mono" | "num";
  value?: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  accent?: boolean;
};

/** 인식 토큰 5개 (성적표에서 결정화되어 칩으로 날아간다). accent 는 마지막 1개만. */
const TOKENS: Token[] = [
  { k: "dept", label: RECOGNITION.department, kind: "text" as const },
  { k: "year", label: RECOGNITION.admissionYear, kind: "mono" as const },
  {
    k: "credits",
    label: `${RECOGNITION.earnedCredits}학점`,
    value: RECOGNITION.earnedCredits,
    suffix: "학점",
    decimals: 0,
    kind: "num" as const,
  },
  {
    k: "gpa",
    label: `GPA ${RECOGNITION.gpa}`,
    value: RECOGNITION.gpa,
    prefix: "GPA ",
    decimals: 1,
    kind: "num" as const,
  },
  {
    k: "count",
    label: `${RECOGNITION.recognizedCourses}과목 인식`,
    value: RECOGNITION.recognizedCourses,
    suffix: "과목 인식",
    decimals: 0,
    kind: "num" as const,
    accent: true,
  },
];

// 토큰 출발 좌표 (textarea 위 산포). mock 고정값이라 비행 경로가 결정적.
const SRC_POS = [
  { left: "7%", top: "16%" },
  { left: "46%", top: "26%" },
  { left: "18%", top: "52%" },
  { left: "58%", top: "60%" },
  { left: "30%", top: "78%" },
];

const GHOST_SAMPLES = [
  "2024-2  데이터사이언스  A0  3.0",
  "2024-2  데이터베이스설계  A-  3.0",
];

/** 자기 타이핑 ghost placeholder: transcript 포맷을 실제로 쳐 보인다. focus/입력 시 정지. */
function useGhostPlaceholder(active: boolean) {
  const reduce = useReducedMotion();
  const [text, setText] = useState("");

  useEffect(() => {
    if (!active || reduce) return;
    let cancelled = false;
    let line = 0;
    let pos = 0;
    let deleting = false;
    function step() {
      if (cancelled) return;
      const full = GHOST_SAMPLES[line % GHOST_SAMPLES.length];
      if (!deleting) {
        pos += 1;
        setText(full.slice(0, pos));
        if (pos >= full.length) {
          setTimeout(() => {
            deleting = true;
            step();
          }, 1200);
          return;
        }
        setTimeout(step, 55);
      } else {
        pos -= 1;
        setText(full.slice(0, Math.max(0, pos)));
        if (pos <= 0) {
          deleting = false;
          line += 1;
          setTimeout(step, 320);
          return;
        }
        setTimeout(step, 26);
      }
    }
    const t = setTimeout(step, 450);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [active, reduce]);

  if (reduce) return GHOST_SAMPLES[0];
  return active ? text : "";
}

export default function VariantA() {
  const reduce = useReducedMotion();
  const [transcript, setTranscript] = useState("");
  const [focused, setFocused] = useState(false);
  const [recog, setRecog] = useState<RecogState>("idle");
  const [selectedJob, setSelectedJob] = useState<JobId | null>(null);
  const [unsureOpen, setUnsureOpen] = useState(false);
  const [highlightJobs, setHighlightJobs] = useState<readonly JobId[] | null>(
    null,
  );
  const [credits, setCredits] = useState(DEFAULT_CREDITS);
  const [creditsOpen, setCreditsOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [activeCourse, setActiveCourse] = useState<string | null>(null);
  const [pulseFirstBlock, setPulseFirstBlock] = useState(false);

  const pulsedRef = useRef(false);
  const pulseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const hasText = transcript.trim().length > 0;
  const recognized = recog === "recognized";
  const ghost = useGhostPlaceholder(!hasText && !focused);

  // 입력 → parsing → recognized (mock: 글자 있으면 인식). 상태전이는 타이머 콜백에서만.
  useEffect(() => {
    if (!hasText) return;
    const t = setTimeout(() => setRecog("recognized"), 620);
    return () => clearTimeout(t);
  }, [hasText]);

  useEffect(() => {
    return () => {
      if (pulseTimerRef.current) clearTimeout(pulseTimerRef.current);
    };
  }, []);

  function handleChange(value: string) {
    setTranscript(value);
    setRecog(value.trim().length > 0 ? "parsing" : "idle");
  }

  function handleSelectJob(id: JobId) {
    setActiveCourse(null);
    setHighlightJobs(null);
    setSelectedJob(id);
  }

  function handleFitSettled() {
    if (pulsedRef.current) return;
    pulsedRef.current = true;
    pulseTimerRef.current = setTimeout(() => setPulseFirstBlock(true), 400);
  }

  const summary = useMemo(
    () => (selectedJob ? planSummary(selectedJob) : null),
    [selectedJob],
  );
  const plan = useMemo(
    () => (selectedJob ? JOB_PLANS[selectedJob] : null),
    [selectedJob],
  );
  const activeCourseData = useMemo(() => {
    if (!plan || !activeCourse) return null;
    return plan.courses.find((c) => c.id === activeCourse) ?? null;
  }, [plan, activeCourse]);

  return (
    <MotionConfig reducedMotion="user" transition={SPRING.smooth}>
      <div className="relative flex min-h-dvh flex-col">
        <div
          aria-hidden
          className="bg-blueprint pointer-events-none fixed inset-0 -z-10 [mask-image:radial-gradient(ellipse_at_top,black,transparent_72%)]"
        />
        <SiteHeader />

        <main className="mx-auto w-full max-w-[1080px] flex-1 px-6 pt-12 pb-28">
          {/* ── 히어로 ───────────────────────────── */}
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

          {/* ── 입력 카드 ────────────────────────── */}
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.06, ease: EASE }}
            className="mt-7"
          >
            <Card className="shadow-card">
              <CardContent className="space-y-3 p-4">
                {/* textarea + scan-line + 토큰 출발 오버레이 */}
                <AnimatePresence initial={false}>
                  {!selectedJob && (
                    <motion.div
                      key="textarea-wrap"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.4, ease: EASE }}
                      className="relative overflow-hidden"
                    >
                      <Textarea
                        value={transcript}
                        onChange={(e) => handleChange(e.target.value)}
                        onFocus={() => setFocused(true)}
                        onBlur={() => setFocused(false)}
                        placeholder={ghost || "복사한 성적표를 여기에 붙여넣기"}
                        className={
                          recognized
                            ? "border-accent min-h-44 border-solid"
                            : "border-line-strong min-h-44 border-2 border-dashed"
                        }
                      />

                      {/* 파서 스캔라인: 1회 훑고 사라짐 */}
                      <AnimatePresence>
                        {recog === "parsing" && !reduce && (
                          <motion.div
                            key="scan"
                            aria-hidden
                            className="bg-accent pointer-events-none absolute inset-x-0 top-0 h-[2px]"
                            initial={{ y: 0, opacity: 0.9 }}
                            animate={{ y: 176, opacity: 0.9 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.62, ease: EASE }}
                          />
                        )}
                      </AnimatePresence>

                      {/* 토큰 출발 span (parsing 동안 textarea 위 산포) */}
                      {recog === "parsing" && !reduce && (
                        <div className="pointer-events-none absolute inset-0">
                          {TOKENS.map((tok, i) => (
                            <motion.span
                              key={tok.k}
                              layoutId={`tok-${tok.k}`}
                              style={{
                                position: "absolute",
                                left: SRC_POS[i].left,
                                top: SRC_POS[i].top,
                                borderRadius: "var(--radius-sm)",
                              }}
                              className="border-line bg-surface/80 text-ink-subtle inline-flex items-center border px-2.5 py-1 text-[0.78rem] font-medium backdrop-blur-[1px]"
                            >
                              {tok.label}
                            </motion.span>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* 상태 행: parsing 스피너 → recognized 칩 (토큰 도착).
                    mode="wait" 를 쓰지 않는 이유: 토큰 출발 span 이 사라지는 커밋과
                    도착 칩이 마운트되는 커밋이 같아야 layoutId FLIP 비행이 연결된다. */}
                <div className="flex min-h-8 items-center">
                  <AnimatePresence initial={false}>
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
                        initial={{ opacity: 1 }}
                        animate={{ opacity: 1 }}
                        className="flex flex-wrap items-center gap-1.5"
                      >
                        {TOKENS.map((tok, i) => (
                          <motion.span
                            key={tok.k}
                            layoutId={reduce ? undefined : `tok-${tok.k}`}
                            style={{ borderRadius: "var(--radius-sm)" }}
                            initial={reduce ? { opacity: 0, y: 4 } : false}
                            animate={{ opacity: 1, y: 0 }}
                            transition={
                              reduce
                                ? { duration: 0.3, delay: 0.05 * i, ease: EASE }
                                : SPRING.snappy
                            }
                            className={
                              tok.accent
                                ? "border-accent/40 bg-accent-wash text-accent-strong inline-flex items-center gap-1.5 border px-2.5 py-1 text-[0.78rem] font-medium"
                                : "border-line bg-surface-muted text-ink-muted inline-flex items-center gap-1.5 border px-2.5 py-1 text-[0.78rem] font-medium"
                            }
                          >
                            {tok.accent && (
                              <span className="bg-accent-strong size-1.5 rounded-full" />
                            )}
                            {tok.kind === "num" ? (
                              <CountUp
                                value={tok.value!}
                                decimals={tok.decimals}
                                prefix={tok.prefix ?? ""}
                                suffix={tok.suffix ?? ""}
                              />
                            ) : (
                              <span
                                className={
                                  tok.kind === "mono"
                                    ? "font-mono tabular-nums"
                                    : undefined
                                }
                              >
                                {tok.label}
                              </span>
                            )}
                          </motion.span>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                <p className="text-ink-subtle text-[0.8rem]">
                  로그인 정보는 받지 않고, 붙여넣은 텍스트는 학점 계산에만 쓰고
                  저장하지 않아요
                </p>
              </CardContent>
            </Card>
          </motion.section>

          {/* ── 직무 선택 (인식 후, 선택 전) ──────── */}
          <AnimatePresence>
            {recognized && !selectedJob && (
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
                </div>

                <div
                  role="radiogroup"
                  aria-label="목표 직무"
                  className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3"
                >
                  {JOBS.map((job, i) => (
                    <MorphJobCard
                      key={job.id}
                      job={job}
                      index={i}
                      selected={false}
                      dimmed={
                        highlightJobs ? !highlightJobs.includes(job.id) : false
                      }
                      onSelect={handleSelectJob}
                    />
                  ))}
                </div>

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
                                  setHighlightJobs(b.jobs);
                                  setUnsureOpen(false);
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

          {/* ── 결과 ─────────────────────────────── */}
          {selectedJob && summary && plan && (
            <motion.section
              aria-label="추천 시간표"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, ease: EASE }}
              className="mt-10"
            >
              <JobToggleBar active={selectedJob} onChange={handleSelectJob} />

              {/* 머리글: 선택 카드가 자라난 자리 (job-${id} 공유요소) */}
              <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
                <motion.div
                  layoutId={reduce ? undefined : `job-${selectedJob}`}
                  style={{ borderRadius: "var(--radius)" }}
                  transition={SPRING.layout}
                  className="border-accent bg-accent-wash inline-flex items-center border px-3.5 py-1.5"
                >
                  <MaskReveal className="text-accent-strong text-[1.05rem] font-semibold tracking-tight">
                    {summary.jobName}
                  </MaskReveal>
                </motion.div>
                <span className="text-ink-muted text-[1.05rem] font-semibold tracking-tight">
                  맞춤 시간표
                </span>
                <Badge variant="accent">충돌 {summary.conflicts}건</Badge>
                <span className="text-ink-muted inline-flex items-baseline gap-1.5 text-[0.9rem]">
                  적합도
                  <FitScore
                    value={summary.fitScore}
                    onSettled={handleFitSettled}
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
              <p className="text-ink-muted mt-1.5 max-w-2xl text-[0.9rem] leading-relaxed break-keep">
                {summary.rationale}
              </p>

              {/* 그리드 + 과목 리스트 */}
              <div className="mt-4 grid gap-4 lg:grid-cols-[1.65fr_1fr]">
                <Card className="shadow-card">
                  <CardContent className="p-4">
                    <MorphGrid
                      courses={plan.courses}
                      selectedCourseId={activeCourse}
                      pulseFirstBlock={pulseFirstBlock}
                      onSelectCourse={(id) =>
                        setActiveCourse((cur) => (cur === id ? null : id))
                      }
                    />

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
                              <span className="text-ink-muted">기르는 역량</span>{" "}
                              {activeCourseData.competency}
                            </p>
                            <p className="text-ink-muted mt-1 text-[0.82rem]">
                              <span className="text-ink-muted">빼면 적합도</span>{" "}
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

                <Card className="shadow-card">
                  <CardContent className="p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <span className="text-[0.9rem] font-semibold tracking-tight">
                        추천 과목
                      </span>
                    </div>
                    <ul className="space-y-2">
                      {plan.courses.map((course, i) => (
                        <CourseRow key={course.id} course={course} index={i} />
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </div>

              {/* 보조 폴드 */}
              <div className="mt-4 flex flex-wrap gap-2">
                <FoldToggle
                  open={creditsOpen}
                  onToggle={() => setCreditsOpen((v) => !v)}
                  label="학점 바꾸기"
                />
                <FoldToggle
                  open={detailOpen}
                  onToggle={() => setDetailOpen((v) => !v)}
                  label="역량 분석"
                />
              </div>

              <AnimatePresence initial={false}>
                {creditsOpen && (
                  <Fold key="credits">
                    <Card className="mt-3">
                      <CardContent className="p-4">
                        <div className="mb-3 flex items-center justify-between">
                          <span className="text-[0.88rem] font-semibold">
                            희망 학점
                          </span>
                          <span className="text-accent-strong font-mono text-sm font-medium tabular-nums">
                            {credits}학점
                          </span>
                        </div>
                        <Slider
                          value={[credits]}
                          min={CREDIT_RANGE.min}
                          max={CREDIT_RANGE.max}
                          step={1}
                          onValueChange={(v) => setCredits(v[0])}
                          aria-label="희망 학점"
                        />
                      </CardContent>
                    </Card>
                  </Fold>
                )}
                {detailOpen && (
                  <Fold key="detail">
                    <Card className="mt-3">
                      <CardContent className="p-5">
                        <div className="grid gap-5 md:grid-cols-2">
                          <div className="min-w-0">
                            <CompetencyChart
                              competencies={JOB_COMPETENCIES[selectedJob]}
                            />
                          </div>
                          <CompetencyBars
                            competencies={JOB_COMPETENCIES[selectedJob]}
                          />
                        </div>
                        <div className="border-accent/35 bg-accent-wash mt-4 flex items-start gap-2.5 rounded-[var(--radius-sm)] border p-3">
                          <span className="bg-accent-strong mt-1.5 size-1.5 shrink-0 rounded-full" />
                          <p className="text-ink text-[0.85rem] leading-relaxed">
                            {JOB_INSIGHT[selectedJob]}
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  </Fold>
                )}
              </AnimatePresence>
            </motion.section>
          )}

          <p className="text-ink-subtle mt-16 text-center text-[0.72rem]">
            예시 데이터로 만든 발표 데모입니다
          </p>
        </main>
      </div>
    </MotionConfig>
  );
}

function FoldToggle({
  open,
  onToggle,
  label,
}: {
  open: boolean;
  onToggle: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="border-line bg-surface text-ink-muted hover:text-ink hover:border-line-strong inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] border px-3 py-1.5 text-[0.82rem] font-medium transition-colors outline-none focus-visible:ring-focus"
    >
      {label}
      <ChevronDown
        className={
          open
            ? "size-3.5 rotate-180 transition-transform"
            : "size-3.5 transition-transform"
        }
        aria-hidden
      />
    </button>
  );
}

function Fold({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.34, ease: EASE }}
      className="overflow-hidden"
    >
      {children}
    </motion.div>
  );
}
