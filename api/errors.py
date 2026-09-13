"""계약(docs/API_계약.md §0)이 정한 에러 형식 — {"error": ..., "detail": ...}.

FastAPI 기본 HTTPException은 {"detail": ...}만 낸다. 프론트가 본문을 읽지는 않지만,
계약을 문서와 다르게 두면 다음 사람이 문서를 못 믿게 된다.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, error: str, detail: str):
        self.status, self.error, self.detail = status, error, detail
        super().__init__(detail)


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status,
                        content={"error": exc.error, "detail": exc.detail})
