"""
FastAPI 앱 진입점.

실행: uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import itinerary, auth, review as review_api, board as board_api, nearby, place
from app.core.config import settings

# 테이블 생성/변경은 이제 Alembic이 담당함 (앱 기동 시 자동 create_all 하던 방식은 제거).
# 서버를 처음 띄우기 전에 반드시 한 번:
#   alembic upgrade head
# 모델을 바꿨으면:
#   alembic revision --autogenerate -m "설명"
#   alembic upgrade head

app = FastAPI(title="K-trip Web API")

# 로컬 개발 기본값은 전체 허용("*")이라 test_client.html을 file://로 열어도 동작하고,
# 배포 환경은 .env의 ALLOWED_ORIGINS로 실제 프론트엔드 도메인만 허용하도록 좁힌다
# (app/core/config.py의 settings.cors_origins 참고).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(itinerary.router)
app.include_router(review_api.router)
app.include_router(board_api.router)
# nearby가 place보다 먼저 와야 함: 둘 다 prefix="/places"를 쓰는데 place.py의
# GET /places/{place_id}가 먼저 매칭되면 "/places/nearby" 요청이 place_id="nearby"로
# 잘못 해석돼버림 (app/api/place.py 상단 주석 참고).
app.include_router(nearby.router)
app.include_router(place.router)


@app.get("/")
def health_check():
    return {"status": "ok"}
