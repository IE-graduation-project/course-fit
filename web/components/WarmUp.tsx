"use client";

import { useEffect } from "react";
import { warmUp } from "@/lib/api";

/**
 * 백엔드 예열 — 화면에는 아무것도 그리지 않는다.
 *
 * 무료 호스팅이라 한동안 요청이 없으면 백엔드가 잠들고, 다음 첫 호출이 20~30초 걸린다.
 * 그 시간이 하필 학과 선택 화면에서 터져서, 사용자는 버튼이 없는 빈 화면을 본다.
 *
 * 랜딩은 어차피 읽는 데 몇 초가 걸리는 화면이다. 여기서 미리 깨워 두면 그 대기가
 * 사용자가 안내를 읽는 시간에 흡수된다. 응답은 세션 캐시에 남아 /start 가 즉시 뜬다.
 */
export default function WarmUp() {
  useEffect(() => {
    warmUp();
  }, []);
  return null;
}
