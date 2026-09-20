"""
DB 연결/세션 관리.

Base는 모델 클래스들이 상속받는 선언적 베이스이고,
get_db()는 FastAPI 라우터에서 Depends(get_db)로 세션을 주입받을 때 쓴다.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 라우터에서 이렇게 사용:

    def endpoint(db: Session = Depends(get_db)):
        ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
