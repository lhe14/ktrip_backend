"""
사용자 모델.

원래 PPT(11~12번 슬라이드)에서 JWT 인증 방식을 쓰기로 한 이유가 명확했음
(웹+모바일 둘 다 지원, 서버가 상태 안 들고 있음, 확장성) - 웹 버전도 그대로 JWT로 감.
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.db.session import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    nickname = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
