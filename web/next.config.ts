import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 프로토타입 단계 — 백엔드 없이 정적 픽스처만으로 돌아간다.
  // 실 API 연결 시 NEXT_PUBLIC_API_BASE 만 채우면 lib/api.ts 가 알아서 갈아탄다.
  reactStrictMode: true,
};

export default nextConfig;
