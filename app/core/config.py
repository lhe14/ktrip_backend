"""
환경변수를 한 곳에서 관리하는 설정 모듈.

TourAPI 서비스키나 DB 접속정보를 코드에 직접 박아넣지 않고
.env 파일에서 읽어오도록 하기 위한 파일이야.
루트에 .env.example을 복사해서 .env로 만들고 값을 채워 넣으면 됨.
"""

import os
from dotenv import load_dotenv

# .env 파일 로드 (프로젝트 루트에 .env가 있다고 가정)
load_dotenv()


class Settings:
    # --- TourAPI 관련 설정 ---
    TOUR_API_SERVICE_KEY: str = os.getenv("TOUR_API_SERVICE_KEY", "")
    # 국문 상품 키 -> KorService2, 영문 상품 키 -> EngService2 (서로 안 맞으면 403 Forbidden.
    # .env.example 상단 주석 참고)
    TOUR_API_BASE_URL: str = os.getenv(
        "TOUR_API_BASE_URL", "https://apis.data.go.kr/B551011/EngService2"
    )
    TOUR_API_MOBILE_OS: str = os.getenv("TOUR_API_MOBILE_OS", "ETC")
    TOUR_API_MOBILE_APP: str = os.getenv("TOUR_API_MOBILE_APP", "KTrip")

    # --- DB 관련 설정 ---
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "mysql+pymysql://user:password@localhost:3306/ktrip"
    )

    # --- 기존 Spring Boot 메인 API 주소 (모바일 앱 전용. 웹 버전은 이 서버 안에서 다 처리하므로 지금은 미사용) ---
    MAIN_API_BASE_URL: str = os.getenv("MAIN_API_BASE_URL", "http://localhost:8080")

    # --- Gemini API (무료 티어) - scripts/label_themes_with_ai.py 전용 ---
    # https://aistudio.google.com/apikey 에서 무료로 발급. 결제 정보 등록 안 해도 무료 티어 사용 가능.
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

    # --- JWT 인증 설정 ---
    # 운영 배포 전에는 반드시 .env에서 랜덤한 값으로 바꿀 것 (예: python -c "import secrets; print(secrets.token_hex(32))")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    # --- CORS 허용 origin ---
    # 로컬 개발은 기본값 "*"(전체 허용)로 편하게 쓰고, 배포 시에는 .env의 ALLOWED_ORIGINS에
    # 실제 프론트엔드 도메인을 콤마로 구분해서 넣는다 (예: https://ktrip.vercel.app,https://ktrip.example.com).
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")

    @property
    def cors_origins(self) -> list[str]:
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


# 다른 모듈에서는 이 settings 객체 하나만 import해서 쓰면 됨
# 예: from app.core.config import settings
settings = Settings()
