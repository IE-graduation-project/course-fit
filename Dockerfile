# course-fit API 서버. 설계: docs/배포_설계.md §4
#
# 요점 둘 —
#  1) DB를 **빌드 타임에** CSV에서 만들어 이미지에 굽는다. 런타임에 외부 DB가 필요 없다.
#  2) 런타임 의존성은 requirements-api.txt(fastapi·uvicorn·pulp)뿐이다. 크롤·LLM 매핑용
#     무거운 패키지(sentence-transformers 등)는 오프라인 전용이라 들어가지 않는다.
FROM python:3.12-slim

WORKDIR /app

# 의존성 먼저 — 코드가 바뀌어도 이 레이어는 캐시된다.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# 시드 DB 빌드. CSV는 .dockerignore 화이트리스트로 9개만 들어온다.
# --validate 까지 돌려서, DB가 깨진 채로 이미지가 만들어지는 일이 없게 한다.
COPY data/ ./data/
COPY db/schema.sql db/ingest.py ./db/
RUN python db/ingest.py --reset && python db/ingest.py --validate

# 애플리케이션
COPY recommender/ ./recommender/
COPY transcript/ ./transcript/
COPY api/ ./api/

# 시드는 이미지 안(읽기 전용), 실제로 여는 DB는 /tmp(쓰기 가능).
# 재시작하면 학생 성적표는 사라진다 — 의도된 동작이다(배포 설계 §6).
ENV COURSE_FIT_SEED_DB=/app/db/app.db \
    COURSE_FIT_DB=/tmp/app.db \
    COURSE_FIT_TTL_HOURS=24 \
    PYTHONUNBUFFERED=1

# 포트는 플랫폼이 정한다 — Render 는 PORT 환경변수로 알려주고, 없으면 7860(로컬 기본).
# shell form 이라 ${PORT} 치환이 되고, exec 를 붙여 uvicorn 이 PID 1 이 되게 한다
# (안 붙이면 sh 가 PID 1 이라 SIGTERM 이 전달되지 않아 종료가 느려진다).
EXPOSE 7860
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 2
