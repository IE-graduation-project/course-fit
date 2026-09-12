import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "course-fit — 다음 학기, 뭘 들어야 할까",
  description:
    "성적표 한 장으로 목표 직무에 부족한 역량을 진단하고, 졸업요건과 시간표 충돌까지 함께 푸는 수강신청 추천.",
};

const PRETENDARD =
  "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css";

/** media="print" 로 받은 글꼴 시트를 다 받은 뒤 all 로 올린다. */
const SWAP_FONT = `(function(){
  var l = document.querySelector('link[data-font="pretendard"]');
  if (!l) return;
  var on = function () { l.media = 'all'; };
  if (l.sheet) on(); else l.addEventListener('load', on);
})();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="" />

        {/*
          Pretendard 를 렌더 블로킹으로 두면 안 된다.
          CPU 4배 감속 + Fast 3G 에서 이 한 줄이 427ms 를 먹었고, 더 나쁜 건
          외부 도메인이라 학교 네트워크에서 jsdelivr 가 막히면 페이지가
          통째로 기다린다는 것이다. 글꼴 하나 때문에 화면이 안 뜰 이유가 없다.

          받는 동안은 globals.css 의 대체 스택(Malgun Gothic 등)으로 즉시 그린다.
        */}
        <link rel="preload" as="style" href={PRETENDARD} />
        <link
          rel="stylesheet"
          href={PRETENDARD}
          media="print"
          data-font="pretendard"
        />
        <script dangerouslySetInnerHTML={{ __html: SWAP_FONT }} />
        <noscript>
          <link rel="stylesheet" href={PRETENDARD} />
        </noscript>
      </head>
      <body>{children}</body>
    </html>
  );
}
