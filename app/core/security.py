"""
비밀번호 해싱 + JWT 발급/검증 유틸.

PPT 12번 슬라이드의 흐름 그대로: 로그인 성공 시 토큰 발급 -> 이후 요청마다 토큰 검증.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

# 참고: passlib+bcrypt 조합은 최근 bcrypt 버전과 호환성 문제가 있어서(버전 감지 오류)
# bcrypt 라이브러리를 직접 사용하는 방식으로 구현함. bcrypt는 72바이트 제한이 있어서
# 그보다 긴 비밀번호는 자동으로 잘라 처리됨 (bcrypt 자체 동작 - 실무에서는 프론트/API 단에서
# 비밀번호 길이를 미리 검증하는 걸 추천).


def hash_password(plain_password: str) -> str:
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    """user_id를 sub 클레임에 담아 JWT 발급"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """토큰을 검증하고 user_id를 반환. 실패하면 jwt 관련 예외를 그대로 던짐 (호출부에서 401 처리)"""
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    return int(payload["sub"])
