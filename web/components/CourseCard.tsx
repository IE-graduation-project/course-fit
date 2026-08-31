"use client";

import type { RecommendedCourse } from "@/lib/types";
import { seqColor } from "@/lib/competency";
import { courseKey } from "./TimetableGrid";

/**
 * 과목 하나가 왜 추천됐는지.
 *
 * 카드가 나르는 사실은 둘뿐이다 — 무슨 과목인가, 어느 갭을 채우나.
 * 그래서 장식도 둘로 줄였다: 근거 막대 하나, 강조 상태 하나.
 * (좌측 컬러바·학수번호 칩·점 범례·졸업요건 알약은 걷어냈다. 졸업요건은
 *  「졸업까지 남은 것」 절이 이미 말하고 있어서 카드마다 반복하면 중복이다.)
 *
 * 막대 색은 hue 를 돌리지 않는다 — share 는 정체가 아니라 크기라서 한 hue 3단이다.
 */
export default function CourseCard({
  course,
  active,
  onHover,
}: {
  course: RecommendedCourse;
  active: boolean;
  onHover?: (id: string | null) => void;
}) {
  const key = courseKey(course);
  const reasons = course.careerReason.filter((r) => r.share >= 0.05);

  // 학수번호-분반이 맨 앞이다. 이 화면을 본 학생이 다음에 하는 일은
  // 수강신청 창에 이 번호를 치는 것이라, 화면에서 제일 실용적인 값이다.
  // (리팩터 때 칩을 장식으로 보고 걷어냈다가 이 값까지 같이 사라졌었다.)
  const meta = [
    `${course.courseId}-${course.section}`,
    `${course.credit}학점`,
    course.area,
    course.timeRaw,
    course.professor,
  ].filter(Boolean);

  return (
    <div
      onMouseEnter={() => onHover?.(key)}
      onMouseLeave={() => onHover?.(null)}
      className={
        "rounded-lg border bg-surface p-4 transition-colors duration-150 " +
        (active ? "border-brand-400 bg-brand-50" : "border-border")
      }
    >
      <h3 className="text-h3 font-semibold leading-snug">{course.name}</h3>
      <p className="mt-1 text-caption text-text-soft">
        <span className="tnum font-semibold text-text-muted">{meta[0]}</span>
        {" · "}
        {meta.slice(1).join(" · ")}
      </p>

      {reasons.length > 0 && (
        <div className="mt-3.5">
          <div className="flex h-2 gap-0.5">
            {reasons.map((r, i) => (
              <div
                key={r.comp}
                className="rounded-sm"
                style={{
                  width: `${r.share * 100}%`,
                  background: seqColor(i),
                }}
              />
            ))}
          </div>
          <p className="mt-2 text-sm text-text-muted">
            {reasons.map((r, i) => (
              <span key={r.comp}>
                {i > 0 && <span className="text-text-soft"> · </span>}
                <span className="text-text">{r.compKo}</span>{" "}
                <span className="tnum text-text-soft">
                  {Math.round(r.share * 100)}%
                </span>
              </span>
            ))}
          </p>
        </div>
      )}
    </div>
  );
}
