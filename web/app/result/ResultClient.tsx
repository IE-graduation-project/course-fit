"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { fetchRecommendation, fetchReference, isMock } from "@/lib/api";
import type { ModeId, Recommendation, Reference } from "@/lib/types";
import TimetableGrid, { courseKey } from "@/components/TimetableGrid";
import CompetencyChart from "@/components/CompetencyChart";
import CourseCard from "@/components/CourseCard";
import { jobRank } from "@/lib/competency";

export default function ResultClient() {
  const params = useSearchParams();
  const initialJob = params.get("job") ?? "DA";
  const initialMode = (params.get("mode") ?? "balanced") as ModeId;

  const [job, setJob] = useState(initialJob);
  const [mode, setMode] = useState<ModeId>(initialMode);
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
  const needTotal = Object.values(rec.need).reduce((a, b) => a + b, 0);
  // 막대는 가장 많이 남은 영역을 100% 로 두고 상대 비교 (합 기준이면 전부 짧아져 안 읽힌다)
  const needMax = Math.max(1, ...Object.values(rec.need));

  return (
    <main className="mx-auto max-w-5xl px-5 py-8 pb-24">
      <header className="mb-7 flex flex-wrap items-center justify-between gap-3">
        <Link href="/" className="text-sm font-semibold text-text-muted hover:text-text">
          ← course-fit
        </Link>
        {isMock() && (
          <span className="rounded-sm bg-warning/15 px-2.5 py-1 text-caption font-semibold text-warning">
            프로토타입 · 고정 데이터
          </span>
        )}
      </header>

      {/* 요약 한 줄 */}
      <div className="fade-up">
        <p className="text-sm text-text-muted">
          {rec.student.deptId} {rec.student.admissionYear}학번 · 목표{" "}
          <b className="text-text">{rec.job.name}</b>
        </p>
        <h1 className="mt-1.5 text-h1 font-bold leading-h">
          이번 학기, 이렇게 들어보세요
        </h1>
      </div>

      {/* 직무 전환 — 눌러서 바로 비교 (switch and see) */}
      <div className="mt-5 flex flex-wrap items-center gap-1.5">
        {[...(ref?.jobs ?? [])]
          .sort((a, b) => jobRank(a.id) - jobRank(b.id))
          .map((j) => (
            <button
              key={j.id}
              onClick={() => setJob(j.id)}
              className={
                "rounded-sm px-3 py-1.5 text-sm font-semibold transition-all " +
                (j.id === job
                  ? "bg-brand-600 text-white"
                  : "border border-border text-text-muted hover:bg-surface-3")
              }
            >
              {j.name}
            </button>
          ))}
      </div>

      {/* 성향 토글 — 즉시 다른 시간표로 */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {(ref?.modes ?? []).map((m) => (
          <button
            key={m.id}
            onClick={() => setMode(m.id)}
            title={m.desc}
            className={
              "rounded-md px-4 py-2 text-sm font-semibold transition-all " +
              (m.id === mode
                ? "bg-ink text-white"
                : "border border-border-strong text-text-muted hover:bg-surface-3")
            }
          >
            {m.label}
          </button>
        ))}
        <span className="tnum text-caption text-text-soft">ε = {rec.params.eps}</span>
      </div>

      {/* 시간표 — 주인공 */}
      <section className="mt-5 grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        <div className="fade-up">
          <div className="mb-2.5 flex flex-wrap items-center gap-2">
            <Stat label="총 학점" value={`${tt.totalCredit}`} />
            <Stat label="과목" value={`${tt.courses.length}`} />
            <Badge ok>시간 충돌 0</Badge>
            <Badge ok>기수강 제외</Badge>
            <Badge ok>선수과목 충족</Badge>
          </div>

          <TimetableGrid
            courses={tt.courses}
            activeId={active}
            onHover={setActive}
          />

          {rec.timetables.length > 1 && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-caption text-text-soft">다른 안</span>
              {rec.timetables.map((t, i) => (
                <button
                  key={t.rank}
                  onClick={() => setAlt(i)}
                  className={
                    "rounded-sm px-3 py-1.5 text-caption font-semibold transition-colors " +
                    (i === alt
                      ? "bg-brand-100 text-brand-700"
                      : "border border-border text-text-muted hover:bg-surface-3")
                  }
                >
                  안 {t.rank}
                  <span className="tnum ml-1.5 opacity-60">
                    {t.totalCredit}학점
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 진단 */}
        <div className="fade-up space-y-5" style={{ animationDelay: "0.1s" }}>
          <section className="card p-5">
            <h2 className="text-h3 font-semibold">
              {rec.job.name}까지 <span className="text-gap">뭐가 모자란가</span>
            </h2>
            <div className="mt-4">
              <CompetencyChart diagnosis={rec.diagnosis} reference={ref} />
            </div>
          </section>

          {needTotal > 0 && (
            <section className="card p-5">
              <h2 className="text-h3 font-semibold">졸업까지 남은 것</h2>
              <ul className="mt-3.5 space-y-2.5">
                {Object.entries(rec.need)
                  .sort((a, b) => b[1] - a[1])
                  .map(([area, credits]) => (
                    <li key={area} className="grid grid-cols-[1fr_auto] items-center gap-3">
                      <span className="flex items-center gap-2.5">
                        <span className="text-sm">{area}</span>
                        <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-3">
                          <span
                            className="block h-full rounded-full bg-grad"
                            style={{
                              width: `${(credits / needMax) * 100}%`,
                            }}
                          />
                        </span>
                      </span>
                      <span className="tnum text-sm font-semibold">{credits}학점</span>
                    </li>
                  ))}
              </ul>
            </section>
          )}
        </div>
      </section>

      {/* 왜 이 과목들인가 */}
      <section className="mt-10">
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
          <div className="card mt-3 space-y-2 bg-surface-3 p-5 text-sm leading-relaxed text-text-muted">
            <p>
              <b className="text-text">σ</b> 지금까지 들은 과목과 성적으로 쌓인 역량
              (많이 들을수록 1에 수렴) → <b className="text-text">gap = max(0, ρ − σ)</b>{" "}
              목표 직무가 원하는 수준 ρ 에서 모자란 만큼 → 과목마다{" "}
              <b className="text-text">Score = Σ gap × 기여도</b> 를 매기고, 시간 충돌·학점
              상하한·기수강·선수과목을 <b className="text-text">제약</b>으로 걸어 정수계획법으로
              풉니다. 1순위는 직무 적합, 2순위는 졸업 진척이고 그 사이를 ε 이 조절합니다.
            </p>
            <p className="text-caption">
              ※ ρ 는 직무 안에서의 상대 중요도, σ 는 절대 누적량이라 엄밀히 같은 척도는
              아닙니다. gap 은 과목을 줄 세우는 순위 신호로만 씁니다.
            </p>
          </div>
        )}

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {tt.courses.map((c, i) => (
            <CourseCard
              key={courseKey(c)}
              course={c}
              index={i}
              active={active === courseKey(c)}
              onHover={setActive}
            />
          ))}
        </div>
      </section>

      <footer className="mt-14 border-t border-border pt-6 text-caption text-text-soft">
        홍익대학교 산업데이터공학과 졸업프로젝트 6조 · 유영준 · 박소연
      </footer>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-baseline gap-1.5 rounded-sm bg-surface px-3 py-1.5 shadow-card">
      <span className="text-caption text-text-soft">{label}</span>
      <span className="tnum text-sm font-bold">{value}</span>
    </span>
  );
}

function Badge({ ok, children }: { ok?: boolean; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-sm bg-success/12 px-2.5 py-1.5 text-caption font-semibold text-success">
      {ok && <span aria-hidden>✓</span>}
      {children}
    </span>
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
            <span className="h-2 w-2 rounded-full bg-brand-500" />
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
