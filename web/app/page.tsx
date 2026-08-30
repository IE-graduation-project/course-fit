import Link from "next/link";

export default function Landing() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col justify-center px-6 py-16">
      <div className="fade-up">
        <span className="inline-flex items-center gap-2 rounded-sm bg-surface-3 px-3 py-1.5 text-caption text-text-muted">
          홍익대학교 산업데이터공학과 졸업프로젝트
        </span>

        <h1 className="mt-7 text-display font-bold leading-display tracking-tight">
          다음 학기,
          <br />
          뭘 들어야 할까?
        </h1>

        <p className="mt-5 max-w-lg text-h3 leading-relaxed text-text-muted">
          성적표를 붙여넣으면 목표 직무에 <b className="text-text">부족한 역량</b>을
          찾고, 졸업요건과 시간표 충돌까지 한 번에 푼 시간표를 만들어 드려요.
        </p>

        <Link
          href="/start"
          className="mt-9 inline-flex items-center gap-2 rounded-md bg-brand-600 px-6 py-3.5 text-body font-semibold text-white shadow-card transition-colors hover:bg-brand-700"
        >
          시작하기
          <span aria-hidden>→</span>
        </Link>

        <p className="mt-3 text-caption text-text-soft">
          약 1분 · 로그인 없음 · 성적표는 저장되지 않아요
        </p>
      </div>

      <div className="mt-16 grid gap-3 sm:grid-cols-3">
        <Pillar
          icon={<IconGap />}
          title="부족한 것부터"
          body="이미 잘하는 건 빼고, 목표 직무 대비 모자란 역량을 채우는 과목을 먼저 고릅니다."
        />
        <Pillar
          icon={<IconGrid />}
          title="겹치지 않게"
          body="시간표 충돌을 제약으로 걸어서 풉니다. 겹치는 시간표는 애초에 나오지 않아요."
        />
        <Pillar
          icon={<IconCap />}
          title="졸업도 같이"
          body="영역별로 남은 졸업 학점을 함께 봅니다. 역량만 좇다 졸업이 밀리지 않게."
        />
      </div>
    </main>
  );
}

function Pillar({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="card fade-up p-5">
      <div className="text-brand-600">{icon}</div>
      <h3 className="mt-3 font-semibold">{title}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-text-muted">{body}</p>
    </div>
  );
}

function IconGap() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="2" y="14" width="6" height="7" rx="1" fill="currentColor" opacity=".35" />
      <rect x="9" y="9" width="6" height="12" rx="1" fill="currentColor" opacity=".6" />
      <rect x="16" y="3" width="6" height="18" rx="1" fill="currentColor" />
    </svg>
  );
}

function IconGrid() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <path d="M3 9h18M9 9v12" stroke="currentColor" strokeWidth="1.8" />
      <rect x="10.5" y="10.5" width="4" height="4" rx=".8" fill="currentColor" />
      <rect x="16" y="15" width="4" height="4" rx=".8" fill="currentColor" opacity=".5" />
    </svg>
  );
}

function IconCap() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 4 2.5 8.5 12 13l9.5-4.5L12 4Z" fill="currentColor" />
      <path
        d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
