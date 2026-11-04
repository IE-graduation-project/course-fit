"use client";

import { useEffect, useState } from "react";

interface Posting {
  title: string;
  url: string;
  company: string;
}

/**
 * 목표 직무의 실제 채용공고 몇 건을 링크로 보여준다(C12).
 *
 * 진단의 "직무가 원하는 수준 ρ"가 어디서 왔는지 — 실제 공고 — 를 드러내 추천 근거의
 * 설득력을 높인다. 공고 본문은 담지 않고 제목·회사·링크만. public/job_postings.json
 * (web/scripts/gen_job_postings.py 로 생성)에서 읽는다.
 */
export default function JobPostings({ jobId, jobName }: { jobId: string; jobName: string }) {
  const [all, setAll] = useState<Record<string, Posting[]> | null>(null);

  useEffect(() => {
    let alive = true;
    fetch("/job_postings.json")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d) => alive && setAll(d))
      .catch(() => alive && setAll({}));
    return () => {
      alive = false;
    };
  }, []);

  const items = all?.[jobId] ?? [];
  if (!all || items.length === 0) return null;

  return (
    <section>
      <h2 className="text-h3 font-semibold">{jobName} 실제 채용공고</h2>
      <p className="mt-1 text-caption leading-relaxed text-text-soft">
        위 진단이 쓰는 “직무가 원하는 수준”은 이런 공고들에서 뽑았어요.
      </p>
      <ul className="mt-3 space-y-2">
        {items.map((p) => (
          <li key={p.url}>
            <a
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-2 rounded-md border border-border bg-surface px-3 py-2 transition-colors hover:border-brand-400 hover:bg-brand-50"
            >
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 break-words text-sm font-medium text-text group-hover:text-brand-800">
                  {p.title}
                </span>
                {p.company && (
                  <span className="mt-0.5 block text-caption text-text-soft">{p.company}</span>
                )}
              </span>
              <IconExternal />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

function IconExternal() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="mt-0.5 shrink-0 text-text-soft"
      aria-hidden
    >
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
    </svg>
  );
}
