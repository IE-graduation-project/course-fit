"""요청 모델.

응답은 dict로 둔다 — 계약 정본이 `web/lib/types.ts`이고, pydantic으로 한 벌 더 정의하면
필드를 추가할 때 두 곳을 고쳐야 한다(결정 ① 과 같은 이유). 응답 모양은 api/serialize.py가
단독으로 책임진다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptRequest(BaseModel):
    """클래스넷 '성적정보 > 전체성적조회' 복붙 텍스트."""
    text: str
    dept: str                      # 유효값은 DB(department ⋈ graduation_requirement)가 정한다
    admissionYear: int = Field(ge=1990, le=2100)


class RecommendRequest(BaseModel):
    studentId: str
    job: str
    mode: str | None = None        # gap | balanced | graduation. eps를 주면 무시된다
    eps: float | None = Field(default=None, ge=0.0, le=1.0)
    maxCredits: int = Field(default=18, ge=1, le=30)
    minCredits: int = Field(default=12, ge=0, le=30)
    topK: int = Field(default=3, ge=1, le=10)
    freeDays: list[int] = Field(default_factory=list)   # 공강으로 비울 요일. 0=월 … 4=금
