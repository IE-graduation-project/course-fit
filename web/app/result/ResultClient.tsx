"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { fetchRecommendation, fetchReference, isMock } from "@/lib/api";
import type { ModeId, Recommendation, Reference } from "@/lib/types";
import TimetableGrid, { courseKey } from "@/components/TimetableGrid";
import CompetencyChart from "@/components/CompetencyChart";
import CourseCard from "@/components/CourseCard";
import JobFitBar from "@/components/JobFitBar";

export default function ResultClient() {
  const params = useSearchParams();
  const router = useRouter();
  const [job, setJob] = useState(params.get("job") ?? "DA");
  const [mode, setMode] = useState<ModeId>(
    (params.get("mode") ?? "balanced") as ModeId,
  );
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [ref, setRef] = useState<Reference | null>(null);
  const [alt, setAlt] = useState(0);
  const [active, setActive] = useState<string | null>(null);
  const [why, setWhy] = useState(false);
  const [loading, setLoading] = useState(true);
  /** 성적표를 낸 적 없이 /result 로 바로 들어왔나 */
  const [demo, setDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReference().then(setRef).catch(console.error);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const saved = sessionStorage.getItem("studentId");
    setDemo(saved === null);
    const studentId = saved ?? "746696b793744f17";
    setError(null);
    fetchRecommendation({ studentId, job, mode })
      .then((r) => {
        if (cancelled) return;
        setRec(r);
        setAlt(0);
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        console.error(e);
        // 이전 결과는 남겨 둔다 — 화면이 통째로 비면 뭘 보고 있었는지 잃는다.
        setError("추천을 불러오지 못했어요. 목표를 다시 눌러보세요.");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [job, mode]);

  useEffect(() => {
    router.replace(`/result?job=${job}&mode=${mode}`, { scroll: false });
  }, [job, mode, router]);

  if (loading && !rec) return <Analyzing />;
  if (!rec) return <Failed />;

  const tt = rec.timetables[alt] ?? rec.timetables[0] ?? null;
  const need = Object.entries(rec.need).sort((a, b) => b[1] - a[1]);
  const needMax = Math.max(1, ...Object.values(rec.need));

  return (
    <main className="mx-auto max-w-5xl px-5 py-8 pb-24">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-3">
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
        {rec.student.deptId} {rec.student.admissionYear}학번 ·{" "}
        {tt === null ? (
          <span>추천 가능한 시간표 없음</span>
        ) : (
          <>
            <span className="tnum">{tt.totalCredit}학점</span> ·{" "}
            <span className="tnum">{tt.courses.length}과목</span>
          </>
        )}
      </p>

      {/* 목표 — 6종을 한 줄에 놓고 적합도까지 같이 (switch and see) */}
      <div className="mt-5">
        <JobFitBar fits={rec.fitByJob} active={job} onChange={setJob} />
        <p className="mt-1.5 text-caption text-text-soft">
          옆 숫자는 지금 성적으로 그 직무에 얼마나 맞는지 (0~100)
        </p>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-3">
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

      <section
        className="mt-6 grid gap-6 transition-opacity duration-200 lg:grid-cols-[1.35fr_1fr]"
        style={{ opacity: loading ? 0.45 : 1 }}
        aria-busy={loading}
      >
        <div>
          {tt === null ? (
            <Infeasible mode={mode} onRelax={() => setMode("graduation")} />
          ) : (
            <>
              <TimetableGrid courses={tt.courses} activeId={active} onHover={setActive} />

              {/* 제약 — 항상 참인 hard 제약이라 초록 배지 셋이 아니라 한 줄이다 */}
              <p className="mt-2.5 flex items-center gap-1.5 text-caption text-text-muted">
                <span className="text-success" aria-hidden>✓</span>
                시간 충돌 없음 · 기수강 제외 · 선수과목 충족
              </p>
            </>
          )}

          {rec.timetables.length > 1 && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-caption text-text-soft">다른 안</span>
              {rec.timetables.map((t, i) => (
                <button
                  key={t.rank}
                  onClick={() => setAlt(i)}
                  aria-pressed={i === alt}
                  className={
                    "min-h-11 rounded-sm border px-4 text-caption transition-colors " +
                    (i === alt
                      ? "border-brand-400 bg-brand-50 font-semibold text-brand-700"
                      : "border-border text-text-muted hover:bg-surface-3")
                  }
                >
                  안 {t.rank}
                </button>
              ))}
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

      <section className="mt-12">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-h2 font-bold">왜 이 과목들일까요?</h2>
          <button
            onClick={() => setWhy((v) => !v)}
            className="-mr-2 inline-flex min-h-11 items-center rounded-sm px-2 text-sm font-semibold text-brand-700 hover:underline"
          >
            {why ? "계산식 접기" : "어떻게 계산했나요?"}
          </button>
        </div>

        {why && (
          <div className="mt-3 space-y-2 rounded-lg bg-surface-3 p-5 text-sm leading-relaxed text-text-muted">
            <p>
              <b className="text-text">σ</b> 지금까지 들은 과목과 성적으로 쌓인 역량
              (많이 들을수록 1에 수렴) → <b className="text-text">gap = max(0, ρ − σ)</b>{" "}
              목표 직무가 원하는 수준 ρ 에서 모자란 만큼 → 과목마다{" "}
              <b className="text-text">Score = Σ gap × 기여도</b> 를 매기고, 시간 충돌·학점
              상하한·기수강·선수과목을 <b className="text-text">제약</b>으로 걸어 정수계획법으로
              풉니다. 1순위는 직무 적합, 2순위는 졸업 진척이고 그 사이를 ε 이 조절합니다
              (지금 ε = <span className="tnum">{rec.params.eps}</span>).
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
            />
          ))}
        </div>
      </section>

      <footer className="mt-16 border-t border-border pt-6 text-caption text-text-soft">
        홍익대학교 산업데이터공학과 졸업프로젝트 6조 · 유영준 · 박소연
      </footer>
    </main>
  );
}

/**
 * ILP 가 못 푼 경우. 계약상 500 이 아니라 timetables: [] 로 온다 —
 * "서비스 고장" 과 "조건이 빡세다" 는 학생에게 완전히 다른 말이라 화면도 달라야 한다.
 */
function Infeasible({
  mode,
  onRelax,
}: {
  mode: ModeId;
  onRelax: () => void;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-8 text-center">
      <p className="text-h3 font-semibold">조건에 맞는 시간표가 없어요</p>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-text-muted">
        학점 범위·시간 충돌·선수과목을 모두 만족하는 조합을 못 찾았습니다.
        남은 과목이 적거나 개설 분반이 겹칠 때 이렇게 됩니다.
      </p>
      {mode !== "graduation" && (
        <button
          onClick={onRelax}
          className="mt-5 inline-flex min-h-11 items-center rounded-md bg-brand-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-brand-700"
        >
          졸업 우선으로 바꿔서 다시 찾기
        </button>
      )}
    </div>
  );
}

function Analyzing() {
  const steps = ["성적표 읽는 중", "역량 계산", "직무 갭 진단", "시간표 최적화"];
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-6">
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
    </main>
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
