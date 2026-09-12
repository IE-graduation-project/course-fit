import type { Metadata } from "next";
import { Suspense } from "react";
import ResultClient from "./ResultClient";

export const metadata: Metadata = {
  title: "추천 시간표 — course-fit",
};

export default function ResultPage() {
  return (
    <Suspense fallback={<div className="min-h-dvh" />}>
      <ResultClient />
    </Suspense>
  );
}
