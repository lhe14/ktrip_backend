"""
장소 점수제.

기존 엑셀 버전에서는 사람이 정한 가중치로 점수를 매겼다면,
여기서는 두 단계로 나눠서 계산한다.

1) 리뷰가 아직 없는 신규/저활동 장소 -> 메타데이터 기반 fallback 점수
   (TourAPI 응답의 이미지 유무, 설명 길이 등으로 최소한의 변별력 부여)
2) 리뷰가 쌓인 장소 -> 실제 평점/좋아요 기반 점수로 대체

** 아키텍처 변경 이력 **
처음엔 "리뷰는 별도 Spring Boot 서버에 있으니 HTTP로 물어봐야 한다"는 전제로 짰었는데,
웹 버전은 리뷰 기능까지 이 FastAPI 프로젝트 하나로 통합하기로 확정되면서 Review 테이블도
같은 DB 안에 있음(app/models/review.py). 그래서 지금은 평범하게 로컬 DB 조회로 처리함.
"""

import math
from dataclasses import dataclass

from sqlalchemy import func

from app.models.place import Place
from app.models.review import Review


@dataclass
class ReviewStats:
    avg_rating: float = 0.0   # 1~5점 평균
    review_count: int = 0
    like_count: int = 0


def get_review_stats(db, place_id: int) -> ReviewStats:
    """이 장소의 리뷰 평점/개수/좋아요 합계를 로컬 Review 테이블에서 집계"""
    row = (
        db.query(
            func.avg(Review.rating),
            func.count(Review.id),
            func.sum(Review.like_count),
        )
        .filter(Review.place_id == place_id)
        .first()
    )

    avg_rating, review_count, like_sum = row if row else (None, 0, None)
    return ReviewStats(
        avg_rating=float(avg_rating) if avg_rating is not None else 0.0,
        review_count=review_count or 0,
        # MySQL은 SUM(INT)을 decimal.Decimal로 반환해서(SQLite는 int/float) 이후 실수 연산과
        # 충돌함 - int로 명시 변환 (실제 로컬 MySQL로 더미데이터 넣다가 TypeError로 발견함)
        like_count=int(like_sum) if like_sum is not None else 0,
    )


def _fallback_score(place: Place) -> float:
    """리뷰가 없을 때 쓰는 최소한의 메타데이터 기반 점수 (0~100)"""
    score = 40.0  # 기본 베이스 점수
    if place.first_image:
        score += 15.0
    if place.overview and len(place.overview) > 50:
        score += 10.0
    return score


def compute_place_score(place: Place, stats: ReviewStats) -> float:
    """
    최종 점수 계산.
    리뷰가 하나도 없으면 fallback, 있으면 평점 중심으로 계산하고
    리뷰 개수가 많을수록(로그 스케일로) 신뢰도 가중치를 조금 더 준다.
    """
    if stats.review_count == 0:
        return _fallback_score(place)

    rating_score = stats.avg_rating * 20  # 5점 만점 -> 100점 만점 환산
    volume_weight = math.log(stats.review_count + 1, 2)  # 리뷰 많을수록 소폭 가산
    like_bonus = min(stats.like_count * 0.5, 10.0)  # 좋아요는 최대 10점까지만 가산

    return round(rating_score + volume_weight + like_bonus, 2)


def refresh_place_score(db, place_id: int) -> float | None:
    """
    장소 하나의 점수만 즉시 재계산 (리뷰 작성/좋아요처럼 실시간 반영이 필요한 이벤트에서 호출).
    전체 재계산(recalculate_all_scores)은 배치용, 이건 단건 이벤트용.
    """
    place = db.query(Place).filter(Place.id == place_id).first()
    if place is None:
        return None

    stats = get_review_stats(db, place_id)
    place.score = compute_place_score(place, stats)
    db.commit()
    return place.score


def recalculate_all_scores(db) -> int:
    """
    전체 Place에 대해 점수를 재계산해서 DB에 반영.
    배치(sync_tourapi.py 직후)나 별도 스케줄러에서 주기적으로 호출하면 됨.
    반환값: 갱신된 장소 수
    """
    places = db.query(Place).all()
    for place in places:
        stats = get_review_stats(db, place.id)
        place.score = compute_place_score(place, stats)

    db.commit()
    return len(places)
