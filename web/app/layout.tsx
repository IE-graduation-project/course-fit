import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "course-fit — 다음 학기, 뭘 들어야 할까",
  description:
    "성적표 한 장으로 목표 직무에 부족한 역량을 진단하고, 졸업요건과 시간표 충돌까지 함께 푸는 수강신청 추천.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://cdn.jsdelivr.net" />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
