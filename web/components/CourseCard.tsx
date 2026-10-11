"use client";

import type { RecommendedCourse } from "@/lib/types";
import { seqColor } from "@/lib/competency";
import { courseKey } from "./TimetableGrid";

/**
 * 과목 하나가 왜 추천됐는지.
 *
 * 카드가 나르는 사실은 셋이다 — 무슨 과목인가, 어느 역량 갭을 채우나, 졸업요건 어디에 꽂히나.
 * 졸업 기여는 원래 「졸업까지 남은 것」 절에 맡기고 카드에서 뺐는데, 그러면 과목을 보는
 * 자리에서 추천 이유가 절반만 보인다(9/14 피드백 ①). 응답의 gradReason 을 그대로 쓴다.
 * 막대 색은 hue 를 돌리지 않는다 — share 는 정체가 아니라 크기라서 한 hue 3단이다.
 */
export default function CourseCard({
  course,
  active,
  onHover,
  areaPlaced,
}: {
  course: RecommendedCourse;
  active: boolean;
  onHover?: (id: string | null) => void;
  /** 이 시간표가 이 과목과 같은 영역에 담은 학점 합. 남은 학점보다 많으면 넘친다고 말한다 */
  areaPlaced?: number;
}) {
  const key = courseKey(course);
  const reasons = course.careerReason.filter((r) => r.share >= 0.05);

  // 학수번호-분반이 맨 앞이다. 이 화면을 본 학생이 다음에 하는 일은
  // 수강신청 창에 이 번호를 치는 것이다.
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
        "print-keep rounded-lg border bg-surface p-4 transition-colors duration-150 " +
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
                {/* 위 막대 조각과 같은 색 — 연한 두 단은 글자에 대비가 모자라 글자 대신 견본에 입힌다 */}
                <span
                  aria-hidden
                  className="mr-1 inline-block h-2 w-2 rounded-[2px] align-[0.05em]"
                  style={{ background: seqColor(i) }}
                />
                <span className="text-text">{r.compKo}</span>{" "}
                <span className="tnum text-text-soft">
                  {Math.round(r.share * 100)}%
                </span>
              </span>
            ))}
          </p>
        </div>
      )}

      {/* 카드마다 「들어갑니다」라고만 하면 같은 영역 과목이 남은 학점보다 많을 때 과장이 된다
          (공통교양 남은 7학점에 15학점을 담아도 다섯 카드가 다 「들어갑니다」였다) */}
      {course.gradReason && (
        <p className="mt-3 border-t border-border pt-2.5 text-caption text-text-soft">
          {course.gradReason.remaining > 0 ? (
            <>
              졸업요건 <span className="font-semibold text-grad-ink">{course.gradReason.area}</span>에
              들어갑니다{" · "}그 영역 남은 학점{" "}
              <span className="tnum text-text-muted">{course.gradReason.remaining}</span>
              {areaPlaced !== undefined && areaPlaced > course.gradReason.remaining && (
                <>
                  {" · "}이 시간표가 이 영역에{" "}
                  <span className="tnum text-text-muted">{areaPlaced}</span>학점을 담아{" "}
                  <span className="tnum text-text-muted">
                    {areaPlaced - course.gradReason.remaining}
                  </span>
                  학점은 넘쳐요
                </>
              )}
            </>
          ) : (
            <>
              <span className="font-semibold text-grad-ink">{course.gradReason.area}</span>은(는) 이미 다
              채웠어요 · 졸업 총학점에만 더해져요
            </>
          )}
        </p>
      )}
    </div>
  );
}
