import type { Metadata } from "next";

// /start 는 "use client" 라 page 에서 metadata 를 못 내보낸다. layout 에서 준다.
export const metadata: Metadata = {
  title: "성적표 입력 — course-fit",
};

export default function StartLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
