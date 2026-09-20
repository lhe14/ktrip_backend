"""
Gemini API(무료 티어) 호출 전담 모듈.

tourapi_client.py랑 같은 스타일: 여기서는 "요청 보내고 텍스트로 응답 돌려주기"만 하고,
프롬프트 구성이나 결과 파싱은 호출하는 쪽(scripts/label_themes_with_ai.py)에서 처리한다.

무료로 쓰는 방법: https://aistudio.google.com/apikey 에서 API 키 발급받아 .env의
GEMINI_API_KEY에 넣으면 됨. 결제 정보 등록 없이 무료 티어 한도 안에서 쓸 수 있음
(한도는 계정/모델마다 다를 수 있으니 label_themes_with_ai.py의 배치 처리 + 딜레이로
호출 횟수 자체를 최소화해뒀음).
"""

import httpx
from app.core.config import settings

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def generate_text(prompt: str, timeout: float = 30.0) -> str:
    """
    프롬프트 하나를 보내고 모델 응답 텍스트를 그대로 반환.
    429(요청 한도 초과)나 그 외 HTTP 에러는 예외를 그대로 던지니 호출부에서 재시도 로직을 둘 것.
    """
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY가 .env에 설정돼 있지 않습니다")

    url = f"{_BASE_URL}/{settings.GEMINI_MODEL}:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    params = {"key": settings.GEMINI_API_KEY}

    response = httpx.post(url, params=params, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Gemini 응답 형식이 예상과 다릅니다: {data}") from e
