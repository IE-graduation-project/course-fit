"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { fetchRecommendation, fetchReference, isMock } from "@/lib/api";
import type { ModeId, Recommendation, Reference } from "@/lib/types";
import TimetableGrid, { courseKey } from "@/components/TimetableGrid";
import CompetencyChart from "@/components/CompetencyChart";
import CourseCard from "@/components/CourseCard";
import JobFitBar from "@/components/JobFitBar";

export default function ResultClient() {
  const params = useSearchParams();
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

  useEffect(() => {
    fetchReference().then(setRef).catch(console.error);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const studentId = sessionStorage.getItem("studentId") ?? "746696b793744f17";
    fetchRecommendation({ studentId, job, mode })
      .then((r) => {
        if (cancelled) return;
        setRec(r);
        setAlt(0);
        setLoading(false);
      })
      .catch((e) => {
        console.error(e);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [job, mode]);

  if (loading && !rec) return <Analyzing />;
  if (!rec) return <Failed />;

  const tt = rec.timetables[alt] ?? rec.timetables[0];
  const need = Object.entries(rec.need).sort((a, b) => b[1] - a[1]);
  const needMax = Math.max(1, ...Object.values(rec.need));

  return (
    <main className="mx-auto max-w-5xl px-5 py-8 pb-24">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <Link href="/" className="text-sm font-semibold text-text-muted hover:text-text">
          ← course-fit
        </Link>
        {isMock() && (
          <span className="text-caption text-text-soft">프로토타입 · 고정 데이터</span>
        )}
      </header>

      <h1 className="text-h1 font-bold leading-h">이번 학기, 이렇게 들어보세요</h1>
      <p className="mt-2 text-sm text-text-muted">
        {rec.student.deptId} {rec.student.admissionYear}학번 ·{" "}
        <span className="tnum">{tt.totalCredit}학점</span> ·{" "}
        <span className="tnum">{tt.courses.length}과목</span>
      </p>

      {/* 목표 — 6종을 한 줄에 놓고 적합도까지 같이 (switch and see) */}
      <div className="mt-5">
        <JobFitBar fits={rec.fitByJob} active={job} onChange={setJob} />
        <p className="mt-1.5 text-caption text-text-soft">
          옆 숫자는 지금 성적으로 그 직무에 얼마나 맞는지 (0~100)
        </p>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-text-muted">성향</span>
          <span className="inline-flex rounded-md border border-border-strong bg-surface-3 p-0.5">
            {(ref?.modes ?? []).map((m) => (
              <button
                key={m.id}
                onClick={() => setMode(m.id)}
                title={m.desc}
                aria-pressed={m.id === mode}
                className={
                  "rounded-sm px-3 py-1.5 text-sm transition-colors " +
                  (m.id === mode
                    ? "bg-surface font-semibold text-text shadow-card"
                    : "text-text-muted hover:text-text")
                }
              >
                {m.label}
              </button>
            ))}
          </span>
        </label>
      </div>

      <section className="mt-6 grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        <div>
          <TimetableGrid courses={tt.courses} activeId={active} onHover={setActive} />

          {/* 제약 — 항상 참인 hard 제약이라 초록 배지 셋이 아니라 한 줄이다 */}
          <p className="mt-2.5 flex items-center gap-1.5 text-caption text-text-muted">
            <span className="text-success" aria-hidden>✓</span>
            시간 충돌 없음 · 기수강 제외 · 선수과목 충족
          </p>

          {rec.timetables.length > 1 && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-caption text-text-soft">다른 안</span>
              {rec.timetables.map((t, i) => (
                <button
                  key={t.rank}
                  onClick={() => setAlt(i)}
                  aria-pressed={i === alt}
                  className={
                    "rounded-sm border px-3 py-1.5 text-caption transition-colors " +
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
            className="text-sm font-semibold text-brand-700 hover:underline"
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
          {tt.courses.map((c) => (
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
