"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, fetchRecommendation, fetchReference, isMock } from "@/lib/api";
import type { CreditLimit, ModeId, Recommendation, Reference, Timetable } from "@/lib/types";
import TimetableGrid, { courseKey } from "@/components/TimetableGrid";
import CompetencyChart from "@/components/CompetencyChart";
import CourseCard from "@/components/CourseCard";
import CopyCodes from "@/components/CopyCodes";
import JobFitBar from "@/components/JobFitBar";
import InfoTip from "@/components/InfoTip";
import { describeShape, diffFromFirst, shape } from "@/lib/altdiff";
import { DAYS, WEEKDAYS } from "@/lib/slots";

/** 시작 화면에서 넣은 학점이 없을 때(옛 세션, 주소로 바로 들어옴) 담을 학점 상한 */
const DEFAULT_CREDITS = 18;
/** 수강가능 최대학점을 모를 때(옛 서버 응답)의 상한 */
const FALLBACK_MAX = 21;

/** 한 학기 최소 학점(학사내규 제4조 ②). 시작 화면의 CREDIT_MIN 과 같다 */
const MIN_CREDITS = 12;
/** 학점 −/+ 나 공강 요일을 누른 뒤 추천을 부르기까지 기다리는 시간. 세 번 누르면 최적화를 세 번 푸는 걸 막는다 */
const STEP_DELAY_MS = 700;
/** 공강으로 고를 수 있는 요일 — 월~금 */
const FREE_DAY_OPTIONS = DAYS.slice(0, WEEKDAYS);

/** 요일 인덱스 목록으로 읽는다. 0~4 의 정수만 남기고 정렬한다 */
const toFreeDays = (v: unknown): number[] =>
  Array.isArray(v)
    ? [...new Set(v.map(Number).filter((d) => Number.isInteger(d) && d >= 0 && d < WEEKDAYS))].sort()
    : [];

export default function ResultClient() {
  const params = useSearchParams();
  const router = useRouter();
  const [job, setJob] = useState(params.get("job") ?? "DA");
  const [mode, setMode] = useState<ModeId>(
    (params.get("mode") ?? "balanced") as ModeId,
  );
  /** 결과 화면에서 고른 학점(주소의 `credits=`). null = 안 골랐다 — 시작 화면에서 넣은 값으로 간다 */
  const [picked, setCredits] = useState<number | null>(() => {
    const v = Number(params.get("credits"));
    return Number.isInteger(v) && v >= 12 && v <= 30 ? v : null;
  });
  /**
   * 이번 학기 수강가능 최대학점 — 성적표를 낼 때 서버가 계산해 준 값(sessionStorage).
   * undefined = 아직 안 읽음, null = 저장된 값 없음(옛 세션). 읽기 전에 주소의 학점을 상한으로
   * 깎으면 FALLBACK_MAX 에 걸려 새로고침할 때마다 21 넘는 선택이 기본값으로 돌아갔다.
   */
  const [limit, setLimit] = useState<CreditLimit | null | undefined>(undefined);
  /** 시작 화면에서 학생이 넣은 최대학점(클래스넷 값). 있으면 이것이 상한이다 */
  const [entered, setEntered] = useState<number | null | undefined>(undefined);
  /** 결과 화면에서 고른 공강 요일(주소의 `free=`). null = 안 골랐다 — 시작 화면에서 넣은 값으로 간다 */
  const [pickedFree, setPickedFree] = useState<number[] | null>(() => {
    const v = params.get("free");
    return v === null ? null : toFreeDays(v.split(",").filter(Boolean));
  });
  /** 시작 화면에서 고른 공강 요일. undefined = 아직 안 읽음 */
  const [enteredFree, setEnteredFree] = useState<number[] | undefined>(undefined);
  const freeDays = pickedFree ?? enteredFree ?? [];
  const freeKey = freeDays.join(",");
  const limitRead = limit !== undefined && entered !== undefined && enteredFree !== undefined;
  const maxCredits = entered ?? limit?.max ?? FALLBACK_MAX;
  /** 추천이 시작하는 학점 — 시작 화면에서 넣은 값 그대로. 18 로 고정하면 20 을 넣고도 18학점 추천을 받았다 */
  const startCredits = entered ?? Math.min(DEFAULT_CREDITS, maxCredits);
  const credits = picked ?? startCredits;
  /** 방금 학점 −/+ 나 공강 요일을 눌렀나 — 그때만 추천 요청을 늦춘다 */
  const stepped = useRef(false);
  const toggleFree = (day: number) => {
    stepped.current = true;
    setPickedFree(
      freeDays.includes(day) ? freeDays.filter((d) => d !== day) : [...freeDays, day].sort(),
    );
  };
  const stepCredits = (d: number) => {
    stepped.current = true;
    setCredits(Math.min(maxCredits, Math.max(MIN_CREDITS, credits + d)));
  };
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [ref, setRef] = useState<Reference | null>(null);
  const [alt, setAlt] = useState(0);
  const [active, setActive] = useState<string | null>(null);
  const [why, setWhy] = useState(false);
  const [loading, setLoading] = useState(true);
  /** 성적표를 낸 적 없이 /result 로 바로 들어왔나 */
  const [demo, setDemo] = useState(false);
  /** 시작 화면에서 「샘플로 먼저 볼래요」로 들어왔나 */
  const [sample, setSample] = useState(false);
  /** 성적표가 없어서 애초에 물어볼 수가 없는 상태 (실 API 일 때만) */
  const [needTranscript, setNeedTranscript] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReference().then(setRef).catch(console.error);
    setSample(sessionStorage.getItem("sample") === "1");
    const raw = sessionStorage.getItem("creditLimit");
    setLimit(raw ? (JSON.parse(raw) as CreditLimit) : null);
    const max = Number(sessionStorage.getItem("creditMax"));
    setEntered(Number.isInteger(max) && max >= 12 && max <= 30 ? max : null);
    try {
      setEnteredFree(toFreeDays(JSON.parse(sessionStorage.getItem("freeDays") ?? "[]")));
    } catch {
      setEnteredFree([]);
    }
  }, []);

  // 주소로 들어온 값이 이 학생의 최대학점을 넘으면 시작 화면에서 넣은 값으로 되돌린다
  useEffect(() => {
    if (limitRead && credits > maxCredits) setCredits(null);
  }, [limitRead, credits, maxCredits]);

  useEffect(() => {
    // 최대학점을 읽기 전, 또는 상한을 넘는 값이 깎이기를 기다리는 동안은 부르지 않는다 — 헛요청이다
    if (!limitRead || credits > maxCredits) return;
    let cancelled = false;
    const saved = sessionStorage.getItem("studentId");
    setDemo(saved === null);

    // 성적표 없이 /result 로 바로 들어온 경우. 픽스처 시절에는 고정 id 로 샘플을
    // 보여줄 수 있었지만, 실 API 에는 그 학생이 없어서 요청이 반드시 404 로 죽는다.
    // 실패할 걸 알면서 던지면 「추천을 불러오지 못했어요」라는 막다른 길이 된다 —
    // 링크를 직접 열거나 세션이 끊긴 사람이 그대로 여기 갇힌다.
    if (saved === null && !isMock()) {
      setNeedTranscript(true);
      setLoading(false);
      return;
    }
    setNeedTranscript(false);

    setLoading(true);
    const studentId = saved ?? "746696b793744f17";
    setError(null);
    const wait = stepped.current ? STEP_DELAY_MS : 0;
    stepped.current = false;
    const timer = setTimeout(() => {
      fetchRecommendation({
        studentId,
        job,
        mode,
        maxCredits: credits,
        freeDays: freeKey === "" ? [] : freeKey.split(",").map(Number),
      })
        .then((r) => {
          if (cancelled) return;
          setRec(r);
          setAlt(0);
          setLoading(false);
        })
        .catch((e) => {
          if (cancelled) return;
          console.error(e);
          setLoading(false);
          // 서버가 성적표를 잃었고 이 탭에도 없으면(시작 화면을 거치지 않은 탭) 다시 누른다고 풀리지
          // 않는다 — 막다른 오류 대신 성적표를 넣는 화면으로 보낸다.
          if (e instanceof ApiError && e.code === "student_not_found") {
            setNeedTranscript(true);
            return;
          }
          // 이전 결과는 남긴다 — 화면이 통째로 비면 뭘 보고 있었는지 잃는다.
          setError(
            e instanceof ApiError && e.code === "server_unavailable"
              ? "서버가 깨어나지 않았어요. 잠시 뒤 목표를 다시 눌러보세요."
              : "추천을 불러오지 못했어요. 목표를 다시 눌러보세요.",
          );
        });
    }, wait);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [job, mode, credits, freeKey, limitRead, maxCredits]);

  useEffect(() => {
    const c = picked === null || picked === startCredits ? "" : `&credits=${picked}`;
    // 시작 화면에서 고른 요일과 같으면 생략한다. 다 끈 것은 `free=` 로 남긴다 — 없으면 고른 요일로 돌아간다
    const f =
      pickedFree === null || freeKey === (enteredFree ?? []).join(",") ? "" : `&free=${freeKey}`;
    router.replace(`/result?job=${job}&mode=${mode}${c}${f}`, { scroll: false });
  }, [job, mode, picked, startCredits, pickedFree, freeKey, enteredFree, router]);

  if (needTranscript) return <NeedTranscript />;
  if (loading && !rec) return <Analyzing />;
  if (!rec) return <Failed />;

  const tt = rec.timetables[alt] ?? rec.timetables[0] ?? null;
  const need = Object.entries(rec.need).sort((a, b) => b[1] - a[1]);
  const needMax = Math.max(1, ...Object.values(rec.need));

  /** 격자에 자리가 없는 과목 — 비대면·논문·실습 분반은 시간 슬롯이 없다.
   *  헤드라인 과목 수와 격자 칸 수가 어긋나 보이는 원인이라 분해해서 적는다(9/14 피드백 ②). */
  const unscheduled = tt?.courses.filter((c) => c.slots.length === 0) ?? [];
  const currentMode = ref?.modes.find((m) => m.id === mode) ?? null;

  /** 대안 셋이 같은 조합이면 버튼을 그리지 않는다 — 눌러도 화면이 안 바뀐다.
   *  분반까지 봐야 한다. 과목명만 비교하면 「같은 과목 다른 시간」을 같은 안으로 읽는다. */
  const hasDistinctAlternatives =
    new Set(
      rec.timetables.map((t) =>
        t.courses
          .map((c) => `${c.courseId}-${c.section}`)
          .sort()
          .join("|"),
      ),
    ).size > 1;

  /** 과목 구성은 같고 분반만 다른 경우. 이때 버튼 라벨(과목 수·적합)이 전부 같아 보여서
   *  무엇을 고르는 건지 알 수 없다 — 다른 게 시간이라는 걸 말해 준다. */
  const alternativesShareCourses =
    rec.timetables.length > 1 &&
    new Set(
      rec.timetables.map((t) =>
        t.courses
          .map((c) => c.courseId)
          .sort()
          .join("|"),
      ),
    ).size === 1;

  return (
    <main className="mx-auto max-w-5xl px-5 py-8 pb-24">
      <header className="print-hide mb-8 flex flex-wrap items-center justify-between gap-3">
        <Link href="/" className="-ml-2 inline-flex min-h-11 items-center rounded-sm px-2 text-sm font-semibold text-text-muted hover:text-text">
          ← course-fit
        </Link>
        {isMock() && (
          <span className="text-caption text-text-soft">프로토타입 · 고정 데이터</span>
        )}
      </header>

      {error && (
        <p
          role="alert"
          className="mb-6 rounded-lg border border-danger/30 bg-danger/8 px-4 py-3 text-sm font-semibold text-danger"
        >
          {error}
        </p>
      )}

      {!demo && sample && (
        <p className="mb-6 rounded-lg border border-border bg-surface-3 px-4 py-3 text-sm text-text-muted">
          <b className="text-text">샘플 학생</b>의 성적표로 본 결과예요. 적합도와 시간표도 그 학생 것입니다.{" "}
          <Link href="/start" className="font-semibold text-brand-700 hover:underline">
            내 성적표로 해보기 →
          </Link>
        </p>
      )}

      {demo && (
        <p className="mb-6 rounded-lg border border-border bg-surface-3 px-4 py-3 text-sm text-text-muted">
          성적표를 넣지 않고 들어오셔서 <b className="text-text">샘플 학생</b> 결과를
          보고 계세요.{" "}
          <Link href="/start" className="font-semibold text-brand-700 hover:underline">
            내 성적표로 해보기 →
          </Link>
        </p>
      )}

      <h1 className="text-h1 font-bold leading-h">이번 학기, 이렇게 들어보세요</h1>
      <p className="mt-2 text-sm text-text-muted">
        {ref?.programs.find((p) => p.dept === rec.student.deptId)?.name ?? rec.student.deptId}{" "}
        {rec.student.admissionYear}학번 ·{" "}
        <span className="tnum">{rec.student.gradeLevel}학년</span> 기준 ·{" "}
        {rec.student.term && (
          <>
            <span className="tnum">{termLabel(rec.student.term)}</span> 개설 강의 ·{" "}
          </>
        )}
        {tt === null ? (
          <span>추천 가능한 시간표 없음</span>
        ) : (
          <>
            <span className="tnum">{tt.totalCredit}학점</span> ·{" "}
            <span className="tnum">{tt.courses.length}과목</span>
            {unscheduled.length > 0 && (
              <span className="text-text-soft">
                {" "}
                (격자에{" "}
                <span className="tnum">
                  {tt.courses.length - unscheduled.length}
                </span>
                , 시간 미지정 <span className="tnum">{unscheduled.length}</span>)
              </span>
            )}
          </>
        )}
      </p>

      {/* 목표 — 6종을 한 줄에 놓고 적합도까지 같이 (switch and see) */}
      <div className="print-hide mt-5">
        <JobFitBar fits={rec.fitByJob} active={job} onChange={setJob} />
        <p className="mt-1.5 text-caption text-text-soft">
          옆 숫자는 지금 성적으로 그 직무에 얼마나 맞는지 (0~100)
        </p>
      </div>

      <div className="print-hide mt-4 flex flex-wrap items-center gap-x-5 gap-y-3">
        {/* 라벨과 버튼 묶음을 한 덩어리로 둔다 — 따로 두면 좁은 화면에서 「학점」 라벨만
            윗줄 끝에 남고 버튼은 아랫줄로 떨어졌다. */}
        <div className="flex items-center gap-x-3">
          <span id="mode-label" className="text-sm text-text-muted">
            성향
          </span>
          <div
            role="group"
            aria-labelledby="mode-label"
            className="inline-flex rounded-md border border-border-strong bg-surface-3 p-0.5"
          >
            {(ref?.modes ?? []).map((m) => (
              <button
                key={m.id}
                onClick={() => setMode(m.id)}
                title={m.desc}
                aria-pressed={m.id === mode}
                className={
                  "min-h-11 rounded-sm px-4 text-sm transition-colors " +
                  (m.id === mode
                    ? "bg-surface font-semibold text-text shadow-card"
                    : "text-text-muted hover:text-text")
                }
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
        {/* 픽스처는 18학점으로만 만들어 두어 고정 데이터일 때는 그리지 않는다 —
            눌러도 결과가 안 바뀌는 버튼이 된다. */}
        {!isMock() && (
          <div className="flex items-center gap-x-3">
            <span id="credits-label" className="text-sm text-text-muted">
              학점
            </span>
            {/* 시작 화면에서 넣을 때와 같은 모양 — 그때 넣은 값을 여기서 줄여 보는 것이라는 게 읽힌다 */}
            <div role="group" aria-labelledby="credits-label" className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => stepCredits(-1)}
                disabled={credits <= MIN_CREDITS}
                aria-label="1학점 줄이기"
                className="min-h-11 w-11 rounded-md border border-border-strong text-lg font-semibold text-text-muted hover:bg-surface-3 disabled:cursor-not-allowed disabled:opacity-35"
              >
                −
              </button>
              <span aria-live="polite" className="tnum w-9 text-center text-sm font-semibold text-text">
                {credits}
              </span>
              <button
                type="button"
                onClick={() => stepCredits(1)}
                disabled={credits >= maxCredits}
                aria-label="1학점 늘리기"
                className="min-h-11 w-11 rounded-md border border-border-strong text-lg font-semibold text-text-muted hover:bg-surface-3 disabled:cursor-not-allowed disabled:opacity-35"
              >
                +
              </button>
            </div>
          </div>
        )}
        {/* 픽스처는 공강 없이 만든 결과뿐이라 고정 데이터일 때는 그리지 않는다 */}
        {!isMock() && (
          <div className="flex items-center gap-x-3">
            <span id="free-label" className="text-sm text-text-muted">
              공강
            </span>
            <div
              role="group"
              aria-labelledby="free-label"
              className="inline-flex rounded-md border border-border-strong bg-surface-3 p-0.5"
            >
              {FREE_DAY_OPTIONS.map((d, day) => {
                const on = freeDays.includes(day);
                return (
                  <button
                    key={d}
                    onClick={() => toggleFree(day)}
                    aria-pressed={on}
                    aria-label={`${d}요일 공강`}
                    className={
                      "min-h-11 min-w-11 rounded-sm px-3 text-sm transition-colors " +
                      (on
                        ? "bg-surface font-semibold text-text shadow-card"
                        : "text-text-muted hover:text-text")
                    }
                  >
                    {d}
                  </button>
                );
              })}
            </div>
          </div>
        )}
        {/* 설명이 title 에만 있으면 마우스를 올려야 보인다 — 무엇을 고른 건지 항상 읽히게 둔다. */}
        {currentMode && (
          <p className="basis-full text-caption text-text-soft">
            {/* 좁은 화면에선 학점 줄 밑에 와서 학점 설명처럼 읽힌다 — 어느 성향의 설명인지 붙인다 */}
            <b className="font-semibold text-text-muted">{currentMode.label}</b>: {currentMode.desc}
          </p>
        )}
        {/* 최대학점이 어디서 나왔는지. 학생이 넣은 값이면 그렇다고, 계산한 값이면 클래스넷 화면과
            같은 항목으로 적어 맞춰 볼 수 있게 한다 */}
        {!isMock() && entered != null && (
          <p className="basis-full text-caption text-text-soft">
            이번 학기 최대 <span className="tnum">{entered}</span>학점 (시작할 때 넣은 값, 클래스넷
            수강신청 → 개인별 수강가능학점 조회) · <span className="tnum">{MIN_CREDITS}</span>학점까지 줄여 볼 수 있어요
          </p>
        )}
        {!isMock() && entered == null && limit && (
          <p className="basis-full text-caption text-text-soft">
            이번 학기 최대 <span className="tnum">{limit.max}</span>학점 = 이수한계{" "}
            <span className="tnum">{limit.base}</span>
            {limit.gpaBonus > 0 && (
              <> + 평점 우수 <span className="tnum">{limit.gpaBonus}</span></>
            )}
            {limit.carry > 0 && (
              <> + 이월 <span className="tnum">{limit.carry}</span></>
            )}
            {" "}(클래스넷 「개인별 수강가능학점 조회」와 같은 식)
          </p>
        )}
      </div>

      {/* 다시 계산하는 동안 이전 결과가 그대로 보이면 「바뀐 게 없다」로 읽힌다. 서버가 깨는 중이면
          30초 가까이 가는데 아무 말이 없었다 — 무엇을 기다리는지 말한다 */}
      {loading && rec && (
        <p
          role="status"
          className="print-hide mt-4 flex items-center gap-2.5 text-sm font-semibold text-brand-700"
        >
          <span className="flex gap-1" aria-hidden>
            <Dot />
            <Dot d={0.2} />
            <Dot d={0.4} />
          </span>
          다시 계산하고 있어요
          <span className="font-normal text-text-soft">
            보통 몇 초, 서버가 잠들어 있었으면 1분쯤
          </span>
        </p>
      )}

      <section
        className="print-stack mt-6 grid gap-6 transition-opacity duration-200 lg:grid-cols-[1.35fr_1fr]"
        style={{ opacity: loading ? 0.45 : 1 }}
        aria-busy={loading}
      >
        <div>
          <div className="print-keep">
          {tt === null ? (
            <Infeasible freeDays={rec.params.freeDays ?? []} />
          ) : (
            <>
              <TimetableGrid
                courses={tt.courses}
                activeId={active}
                onHover={setActive}
                freeDays={rec.params.freeDays ?? []}
              />

              {/* 제약 — 응답의 constraints 를 실제로 읽는다. 우리가 보증한다고 내건 것이라
                  고정 문자열로 두면 백엔드가 false 를 줘도 화면은 계속 충족했다고 말한다. */}
              <ConstraintLine constraints={rec.constraints} />

              {/* 성향을 바꾸면 무엇이 달라지는지 — 응답에 오는 두 목적함수 값을 그대로 쓴다 */}
              <TimetableMeters tt={tt} />
            </>
          )}
          </div>

          <div className="print-hide">
            {tt !== null && <CopyCodes courses={tt.courses} />}
          </div>

          {/* 대안이 서로 같으면 버튼을 안 그린다 — 눌러도 아무 일도 안 일어나는 버튼은 두지 않는다.
              무엇이 다른지 못 고르면 「안 1/2/3」은 라벨일 뿐이라 과목 수와 적합도를 같이 적는다. */}
          {rec.timetables.length > 1 && hasDistinctAlternatives && (
            <div className="print-hide mt-4 flex flex-wrap items-center gap-2">
              <span className="text-caption text-text-soft">
                {alternativesShareCourses ? "같은 과목, 다른 분반" : "다른 안"}
              </span>
              {rec.timetables.map((t, i) => (
                <button
                  key={t.rank}
                  onClick={() => setAlt(i)}
                  aria-pressed={i === alt}
                  className={
                    "flex min-h-11 flex-col items-start justify-center rounded-sm border px-3 py-1 text-caption leading-tight transition-colors " +
                    (i === alt
                      ? "border-brand-400 bg-brand-50 font-semibold text-brand-700"
                      : "border-border text-text-muted hover:bg-surface-3")
                  }
                >
                  <span>안 {t.rank}</span>
                  {/* 과목이 같으면 이 값도 셋 다 같다 — 같은 수를 세 번 적으면 노이즈다 */}
                  {!alternativesShareCourses && (
                    <span className="text-text-soft">
                      <span className="tnum">{t.courses.length}</span>과목 · 보완{" "}
                      <span className="tnum">{fitIndex(t)}</span>
                    </span>
                  )}
                </button>
              ))}
              {/* 무엇이 다른지는 눌러 보기 전엔 몰랐다(#75). 늘 펼쳐 두기엔 길어서 ⓘ 로 연다 */}
              <InfoTip label="안마다 무엇이 다른지">
                <AltDiffs timetables={rec.timetables} />
              </InfoTip>
            </div>
          )}
        </div>

        <div className="space-y-6">
          <section>
            <h2 className="text-h3 font-semibold">
              {rec.job.name}까지 뭐가 모자란가
            </h2>
            <div className="mt-3.5">
              <CompetencyChart diagnosis={rec.diagnosis} reference={ref} />
            </div>
          </section>

          {need.length > 0 && (
            <section>
              <h2 className="text-h3 font-semibold">졸업까지 남은 것</h2>
              {/* 어느 교육과정을 기준으로 셌는지 밝힌다. 입학년도와 다를 수 있다 —
                  2025학번 경영은 2022 교육과정을 따른다. 학생이 직접 확인할 수 있어야 한다. */}
              <p className="mt-1 text-caption text-text-soft">
                지금까지 들은 과목 기준(이번 추천 전) · {rec.student.requirementYear}학년도 교육과정
              </p>
              <ul className="mt-3.5 space-y-2.5">
                {need.map(([area, credits]) => (
                  <li
                    key={area}
                    className="grid grid-cols-[7rem_1fr_3.25rem] items-center gap-3"
                  >
                    <span className="truncate text-sm text-text-muted">{area}</span>
                    <span className="h-1.5 overflow-hidden rounded-full bg-surface-3">
                      <span
                        className="block h-full rounded-full"
                        style={{
                          width: `${(credits / needMax) * 100}%`,
                          background: "var(--color-grad)",
                        }}
                      />
                    </span>
                    <span className="tnum text-right text-sm">{credits}학점</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </section>

      <section
        className="mt-12 transition-opacity duration-200"
        style={{ opacity: loading ? 0.45 : 1 }}
        aria-busy={loading}
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-h2 font-bold">왜 이 과목들일까요?</h2>
          <button
            onClick={() => setWhy((v) => !v)}
            className="print-hide -mr-2 inline-flex min-h-11 items-center rounded-sm px-2 text-sm font-semibold text-brand-700 hover:underline"
          >
            {why ? "계산식 접기" : "어떻게 계산했나요?"}
          </button>
        </div>

        {/* 토글 안에만 두면 아무도 안 편다. 한 줄 요약은 항상 보이게 두고 식은 접어 둔다. */}
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-muted">
          목표 직무가 요구하는 역량 중 <b className="text-text">지금 모자란 것</b>을 크게
          채우는 과목부터 고르고, 시간 충돌·학점 범위·기수강·선수과목·수강 학년을 제약으로 걸어
          풀었습니다. 카드의 비율은 그 과목이{" "}
          <b className="text-text">어느 역량 갭을 채우는지</b>입니다.
        </p>

        {why && (
          <div className="mt-3 space-y-2 rounded-lg bg-surface-3 p-5 text-sm leading-relaxed text-text-muted">
            <p>
              <b className="text-text">σ</b> 지금까지 들은 과목과 성적으로 쌓인 역량
              (많이 들을수록 1에 수렴) → <b className="text-text">gap = max(0, ρ − σ)</b>{" "}
              목표 직무가 원하는 수준 ρ 에서 모자란 만큼 → 과목마다{" "}
              <b className="text-text">Score = Σ gap × 기여도</b> 를 매기고, 시간 충돌·학점
              상하한·기수강·선수과목·수강 학년을 <b className="text-text">제약</b>으로 걸어 정수계획법으로
              풉니다. 먼저 역량 보완이 가장 큰 시간표를 찾고, 그 값을 ε 만큼 양보하는 범위 안에서
              졸업 반영이 가장 큰 시간표를 고릅니다. ε 이 클수록 졸업 쪽으로 기웁니다(역량 우선 0,
              균형 0.3, 졸업 우선 0.6 · 지금 <span className="tnum">{rec.params.eps}</span>).
            </p>
            <p className="text-caption">
              ※ ρ 는 직무 안에서의 상대 중요도, σ 는 절대 누적량이라 엄밀히 같은 척도는
              아닙니다. gap 은 과목을 줄 세우는 순위 신호로만 씁니다.
            </p>
          </div>
        )}

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {(tt?.courses ?? []).map((c) => (
            <CourseCard
              key={courseKey(c)}
              course={c}
              active={active === courseKey(c)}
              onHover={setActive}
              areaPlaced={(tt?.courses ?? [])
                .filter((o) => o.area === c.area)
                .reduce((n, o) => n + o.credit, 0)}
            />
          ))}
        </div>
      </section>

      <footer className="mt-16 border-t border-border pt-6 text-caption text-text-soft">
        개설 강의와 졸업요건 데이터를 바탕으로 계산한 추천입니다. 신청 전에 학사 공지와
        최종 개설 여부를 함께 확인하세요.
      </footer>
    </main>
  );
}

/**
 * 직무 적합 지수 (0~100).
 *
 * careerfit = Σ credit·Score 라 학점 수에 딸려 커진다. 학점으로 나누면 「고른 과목들의
 * 학점당 평균 갭 보완도」가 되고, Score_c = Σ_k gap_k·w_{c,k} 는 gap·w 가 각각 0~1 이라
 * 사실상 0~1 범위다. 그래서 100 을 곱해 그대로 읽을 수 있는 수가 된다.
 * 절대 눈금이 아니라 성향·대안을 견주는 상대 지표로만 쓴다.
 */
/** "2026-2" → "2026학년도 2학기". 계절학기 코드(S, W)도 읽히게 */
function termLabel(term: string) {
  const [y, s] = term.split("-");
  const name = { "1": "1학기", "2": "2학기", S: "여름 계절학기", W: "겨울 계절학기" }[s] ?? s;
  return `${y}학년도 ${name}`;
}

/** ⓘ 안의 내용 — 안 1의 한 주 모양, 그리고 안 2·3이 그와 다른 점 */
function AltDiffs({ timetables }: { timetables: Timetable[] }) {
  const MAX_LINES = 4;
  return (
    <span className="block space-y-2">
      <span className="block">
        <b className="font-semibold text-text">안 1</b> {describeShape(shape(timetables[0]))}
      </span>
      {diffFromFirst(timetables).map((d) => {
        const lines = [...d.changes, ...d.week];
        return (
          <span key={d.rank} className="block">
            <b className="font-semibold text-text">안 {d.rank}</b>
            {lines.length === 0 && " 안 1과 같은 시간"}
            {lines.slice(0, MAX_LINES).map((l) => (
              <span key={l} className="block pl-3">
                {l}
              </span>
            ))}
            {lines.length > MAX_LINES && (
              <span className="block pl-3 text-text-soft">외 {lines.length - MAX_LINES}개</span>
            )}
          </span>
        );
      })}
    </span>
  );
}

function fitIndex(t: Timetable) {
  if (t.totalCredit <= 0) return 0;
  return Math.round((t.careerfit / t.totalCredit) * 100);
}

const CONSTRAINT_LABEL: Record<keyof Recommendation["constraints"], string> = {
  noTimeConflict: "시간 충돌 없음",
  creditBounds: "학점 범위 준수",
  excludeTaken: "기수강 제외",
  prereqSatisfied: "선수과목 충족",
  gradeEligible: "수강 학년 충족",
};

/** 만족한 제약은 한 줄로, 깨진 제약은 경고로. 간판으로 내건 보증이라 실제 값을 읽는다. */
function ConstraintLine({
  constraints,
}: {
  constraints: Recommendation["constraints"];
}) {
  const entries = Object.entries(constraints) as [
    keyof Recommendation["constraints"],
    boolean,
  ][];
  const unmet = entries.filter(([, ok]) => !ok);

  if (unmet.length > 0) {
    return (
      <p
        role="alert"
        className="mt-2.5 flex items-start gap-1.5 text-caption font-semibold text-danger"
      >
        <span aria-hidden>⚠</span>
        <span>
          만족하지 못한 조건 —{" "}
          {unmet.map(([k]) => CONSTRAINT_LABEL[k]).join(" · ")}. 그대로 신청하지 마세요.
        </span>
      </p>
    );
  }

  return (
    <p className="mt-2.5 flex items-center gap-1.5 text-caption text-text-muted">
      <span className="text-success" aria-hidden>
        ✓
      </span>
      {entries.map(([k]) => CONSTRAINT_LABEL[k]).join(" · ")}
    </p>
  );
}

/**
 * 성향을 바꾸면 무엇이 달라지는가.
 *
 * 응답에는 두 목적함수 값이 오는데 화면이 안 그리고 있었다 — 그래서 「역량 우선」과
 * 「졸업 우선」이 같은 화면으로 보였다(9/14 피드백 ⑧). 둘을 같은 0~100 눈금에
 * 나란히 두면 이 성향이 무엇을 얻고 무엇을 내줬는지 한눈에 읽힌다.
 */
function TimetableMeters({ tt }: { tt: Timetable }) {
  const fit = fitIndex(tt);
  const gradPct =
    tt.totalCredit > 0
      ? Math.round((tt.gradProgress / tt.totalCredit) * 100)
      : 0;

  const rows = [
    {
      label: "역량 보완",
      hint: "이 시간표가 목표 직무의 모자란 역량을 얼마나 채우나. 위 직무 옆 숫자(지금 적합도)와 다른 값이고, 성향과 대안끼리 견주는 용도",
      value: fit,
      color: "var(--color-gap)",
      right: <span className="tnum">{fit}</span>,
    },
    {
      label: "졸업 반영",
      hint: `${tt.totalCredit}학점 중 졸업요건에 실제로 꽂히는 학점`,
      value: gradPct,
      color: "var(--color-grad)",
      right: (
        <span className="tnum">
          {tt.gradProgress}/{tt.totalCredit}
        </span>
      ),
    },
  ];

  return (
    <dl className="mt-4 space-y-2.5">
      {rows.map((r) => (
        <div
          key={r.label}
          className="grid grid-cols-[5rem_1fr_3.25rem] items-center gap-3"
        >
          <dt className="text-sm text-text-muted" title={r.hint}>
            {r.label}
          </dt>
          <dd className="h-1.5 overflow-hidden rounded-full bg-surface-3">
            <span
              className="block h-full rounded-full transition-[width] duration-300"
              style={{
                width: `${Math.max(0, Math.min(100, r.value))}%`,
                background: r.color,
              }}
            />
          </dd>
          <dd className="text-right text-sm text-text-muted">{r.right}</dd>
          {/* 마우스를 올려야만 보이는 설명은 휴대폰에서 영영 안 보인다 */}
          <dd className="col-span-3 -mt-1.5 text-caption text-text-soft">{r.hint}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * ILP 가 못 푼 경우. 계약상 500 이 아니라 timetables: [] 로 온다 —
 * "서비스 고장" 과 "조건이 빡세다" 는 학생에게 완전히 다른 말이라 화면도 달라야 한다.
 */
function Infeasible({
  freeDays,
}: {
  /** 이 결과에 적용된 공강 요일 */
  freeDays: number[];
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-8 text-center">
      <p className="text-h3 font-semibold">조건에 맞는 시간표가 없어요</p>
      {/* 성향은 가능한 조합 가운데 무엇을 고를지만 정해서, 바꿔도 없던 조합이 생기지 않는다 —
          「졸업 우선으로 다시 찾기」 버튼은 같은 화면만 다시 냈다. 학생이 풀 수 있는 조건은 공강뿐이다 */}
      {freeDays.length > 0 ? (
        <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-text-muted">
          <b className="text-text">{freeDays.map((d) => DAYS[d]).join("·")}요일</b>을 비우고는 한 학기
          최소 <span className="tnum">{MIN_CREDITS}</span>학점을 채우는 시간표를 못 찾았어요. 위에서
          공강 요일을 줄여 보세요.
        </p>
      ) : (
        <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-text-muted">
          학점 범위·시간 충돌·선수과목·수강 학년을 모두 만족하는 조합을 못 찾았습니다.
          남은 과목이 적거나 개설 분반이 겹칠 때 이렇게 됩니다.
        </p>
      )}
    </div>
  );
}

/**
 * 성적표 없이 결과 주소로 바로 들어온 경우.
 * 「고장났다」가 아니라 「아직 넣은 게 없다」이므로 실패 화면과 말이 달라야 한다.
 */
function NeedTranscript() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6 text-center">
      <p className="text-h3 font-semibold">먼저 성적표를 넣어주세요</p>
      <p className="mt-2 text-sm leading-relaxed text-text-muted">
        추천은 성적표에서 계산하기 때문에, 넣은 것이 없으면 보여드릴 결과가 없어요.
        붙여넣기만 하면 되고 약 1분 걸립니다.
      </p>
      <Link
        href="/start"
        className="mx-auto mt-6 inline-flex min-h-11 items-center rounded-md bg-brand-600 px-6 text-sm font-semibold text-white transition-colors hover:bg-brand-700"
      >
        시작하기
      </Link>
    </main>
  );
}

function Analyzing() {
  const steps = ["성적표 읽는 중", "역량 계산", "직무 갭 진단", "시간표 최적화"];
  // 목록만 서 있으면 멈춘 화면인지 계산 중인지 모른다 — 움직이는 표시와 걸리는 시간을 같이 둔다
  return (
    <main
      role="status"
      aria-live="polite"
      className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6"
    >
      <p className="mb-5 flex items-center gap-2.5 text-sm font-semibold text-text">
        <span className="flex gap-1" aria-hidden>
          <Dot />
          <Dot d={0.2} />
          <Dot d={0.4} />
        </span>
        시간표를 계산하고 있어요
      </p>
      <div className="space-y-3">
        {steps.map((s, i) => (
          <div
            key={s}
            className="fade-up flex items-center gap-3"
            style={{ animationDelay: `${i * 0.18}s` }}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
            <span className="text-text-muted">{s}</span>
          </div>
        ))}
      </div>
      <p className="mt-5 text-caption leading-relaxed text-text-soft">
        보통 몇 초면 끝나요. 한동안 아무도 안 썼다면 서버가 깨는 데 1분쯤 걸려요.
      </p>
    </main>
  );
}

function Dot({ d = 0 }: { d?: number }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 rounded-full bg-brand-500"
      style={{ animation: `fadeIn .6s ${d}s infinite alternate` }}
    />
  );
}

function Failed() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6 text-center">
      <p className="text-text-muted">추천을 불러오지 못했어요.</p>
      <Link href="/start" className="mt-4 font-semibold text-brand-700 hover:underline">
        처음부터 다시
      </Link>
    </main>
  );
}
