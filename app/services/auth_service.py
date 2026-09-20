"""
회원가입/로그인 비즈니스 로직.
"""

from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import hash_password, verify_password


class AuthError(Exception):
    """이메일 중복, 로그인 실패 등 인증 관련 오류를 라우터에서 구분해서 처리하기 위한 커스텀 예외"""


def register_user(db: Session, email: str, nickname: str, password: str) -> User:
    if db.query(User).filter(User.email == email).first():
        raise AuthError("이미 가입된 이메일입니다")
    if db.query(User).filter(User.nickname == nickname).first():
        raise AuthError("이미 사용 중인 닉네임입니다")

    user = User(email=email, nickname=nickname, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise AuthError("이메일 또는 비밀번호가 올바르지 않습니다")
    return user
